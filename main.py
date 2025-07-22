from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import re
import logging
import traceback
import tempfile
import os
import subprocess
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="API de Transcrição de Vídeo do YouTube")


class HealthCheckResponse(BaseModel):
    status: str


class TranscriptionRequest(BaseModel):
    url: str
    language: str = "pt"


class TranscriptionResponse(BaseModel):
    transcription: str


def extract_video_id(url: str) -> str:
    """Extrai o ID do vídeo da URL do YouTube."""
    if re.match(r'^[0-9A-Za-z_-]{11}$', url):
        return url
    
    patterns = [
        r"(?:v=|/)([0-9A-Za-z_-]{11})",
        r"youtu.be/([0-9A-Za-z_-]{11})",
        r"watch\?v=([0-9A-Za-z_-]{11})",
        r"embed/([0-9A-Za-z_-]{11})",
        r"watch\?.*&v=([0-9A-Za-z_-]{11})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    raise ValueError("ID do vídeo não encontrado na URL.")


def get_subtitles_with_ytdlp(video_url: str, language: str = "pt") -> str:
    """Obtém legendas usando yt-dlp."""
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [language, 'pt-BR', 'pt-PT', 'en'],
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Verifica legendas disponíveis
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            # Prioridade: legendas manuais em português
            for lang in ['pt', 'pt-BR', 'pt-PT']:
                if lang in subtitles:
                    logger.info(f"Encontradas legendas manuais em {lang}")
                    for sub in subtitles[lang]:
                        if sub.get('ext') == 'json3':
                            logger.info(f"Baixando legendas de: {sub['url']}")
                            sub_data = ydl.urlopen(sub['url']).read().decode('utf-8')
                            logger.info(f"Dados das legendas baixados: {len(sub_data)} bytes")
                            return parse_json3_subtitles(sub_data)
            
            # Segunda opção: legendas automáticas em português
            for lang in ['pt', 'pt-BR', 'pt-PT']:
                if lang in automatic_captions:
                    logger.info(f"Encontradas legendas automáticas em {lang}")
                    for sub in automatic_captions[lang]:
                        if sub.get('ext') == 'json3':
                            logger.info(f"Baixando legendas automáticas de: {sub['url']}")
                            sub_data = ydl.urlopen(sub['url']).read().decode('utf-8')
                            logger.info(f"Dados das legendas automáticas baixados: {len(sub_data)} bytes")
                            return parse_json3_subtitles(sub_data)
            
            # Terceira opção: legendas em inglês para traduzir
            if 'en' in subtitles or 'en' in automatic_captions:
                subs_dict = subtitles.get('en', automatic_captions.get('en', []))
                for sub in subs_dict:
                    if sub.get('ext') == 'json3':
                        sub_data = ydl.urlopen(sub['url']).read().decode('utf-8')
                        transcription = parse_json3_subtitles(sub_data)
                        return f"[Transcrição em inglês - tradução automática não disponível]\n\n{transcription}"
            
            # Lista todas as legendas disponíveis para debug
            all_langs = list(subtitles.keys()) + list(automatic_captions.keys())
            if all_langs:
                raise ValueError(f"Legendas disponíveis apenas em: {', '.join(set(all_langs))}")
            else:
                raise ValueError("Nenhuma legenda disponível para este vídeo")
                
    except Exception as e:
        logger.error(f"Erro ao obter legendas com yt-dlp: {e}")
        raise


def parse_json3_subtitles(json_data: str) -> str:
    """Converte formato JSON3 do YouTube em texto de forma mais robusta."""
    try:
        data = json.loads(json_data)
        text_parts = []
        
        for event in data.get('events', []):
            if not isinstance(event, dict):
                continue

            # Coleta todo o texto do evento, incluindo aninhados
            texts = []
            
            def extract_text_from_event(e):
                if isinstance(e, dict):
                    if 'segs' in e:
                        for seg in e['segs']:
                            if isinstance(seg, dict) and 'utf8' in seg:
                                texts.append(seg['utf8'])
                    # Extrai texto de outras chaves comuns
                    for key in ['aAppend', 'wWinId']:
                         if key in e and isinstance(e[key], str):
                                texts.append(e[key])
                elif isinstance(e, list):
                    for item in e:
                        extract_text_from_event(item)

            extract_text_from_event(event)
            
            # Processa e limpa o texto coletado
            for text in texts:
                cleaned_text = text.replace('\n', ' ').strip()
                if cleaned_text:
                    text_parts.append(cleaned_text)

        # Junta todo o texto e normaliza os espaços
        full_text = ' '.join(text_parts)
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        logger.info(f"Texto extraído tem {len(full_text)} caracteres")
        if len(full_text) < 100:
            logger.warning(f"Transcrição muito curta. Dados JSON (primeiros 300 chars): {json_data[:300]}")
            
        return full_text
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro de decodificação JSON: {e}")
        logger.error(f"Dados recebidos (primeiros 300 chars): {json_data[:300]}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao processar JSON3: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


@app.get("/", response_model=HealthCheckResponse)
async def health_check():
    return HealthCheckResponse(status="Healthy")


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(request: TranscriptionRequest):
    try:
        video_id = extract_video_id(request.url)
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        logger.info(f"Extraindo transcrição para vídeo ID: {video_id}")
        
        try:
            transcription = get_subtitles_with_ytdlp(video_url, request.language)
            
            if transcription and transcription.strip():
                return TranscriptionResponse(transcription=transcription.strip())
            else:
                raise HTTPException(
                    status_code=404,
                    detail="Transcrição obtida mas está vazia"
                )
                
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Erro ao processar transcrição: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar transcrição: {str(e)}"
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Erro inesperado: {str(e)}")


@app.get("/test/{video_id}")
async def test_video(video_id: str):
    """Endpoint de teste para verificar disponibilidade de transcrições"""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    results = {
        "video_id": video_id,
        "available_subtitles": {},
        "automatic_captions": {},
        "video_info": {},
        "errors": []
    }
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            results["available_subtitles"] = list(info.get('subtitles', {}).keys())
            results["automatic_captions"] = list(info.get('automatic_captions', {}).keys())
            results["video_info"] = {
                "title": info.get('title'),
                "duration": info.get('duration'),
                "uploader": info.get('uploader'),
                "upload_date": info.get('upload_date')
            }
            
    except Exception as e:
        results["errors"].append({"error": str(e), "type": type(e).__name__})
    
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")