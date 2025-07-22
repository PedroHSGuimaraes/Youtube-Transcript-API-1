# YouTube Transcript API

This project provides a FastAPI-based service for transcribing YouTube videos. It uses the `langchain_community.document_loaders.YoutubeLoader` to fetch and process video transcripts.

## Features

- Accepts a YouTube video URL and language code.
- Returns the full transcription of the video in the specified language.
- Built with FastAPI for high performance and easy deployment.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/your-username/Youtube-Transcript-API.git
    cd Youtube-Transcript-API
    ```

2. Create a virtual environment and activate it:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Start the FastAPI server:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```

2. Use the `/transcribe` endpoint to get a video transcription:
    - **Endpoint**: `POST /transcribe`
    - **Request Body**:
      ```json
      {
         "url": "https://www.youtube.com/watch?v=example",
         "language": "pt"
      }
      ```
    - **Response**:
      ```json
      {
         "transcription": "Full transcription of the video."
      }
      ```

## DEMO

You can test the API using `curl` or any HTTP client like Postman:
```bash
curl -X POST "https://yt-transcript.leapcell.app/transcribe" \
-H "Content-Type: application/json" \
-d '{"url": "https://www.youtube.com/watch?v=example", "language": "pt"}'
```

## Dependencies

- `fastapi`
- `uvicorn`
- `pydantic`
- `langchain_community`

## License

This project is licensed under the MIT License.

## Acknowledgments

Special thanks to the developers of FastAPI and LangChain for their amazing tools.
