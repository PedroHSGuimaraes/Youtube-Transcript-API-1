# Use the official Python 3.13 Alpine image as the base image
FROM python:3.13-alpine

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file if it exists and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the application port
EXPOSE 8000

# Set the command to run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]