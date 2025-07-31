# Video Merger API

A FastAPI application for merging videos stored in MinIO S3 buckets and uploading videos to YouTube.

## Features

- Download videos from MinIO S3 buckets via URLs
- Merge multiple MP4 videos into a single video file
- Upload the merged video to a target S3 bucket
- **NEW**: Upload videos directly to YouTube via YouTube Data API v3
- Support for both MinIO and AWS S3
- Automatic cleanup of temporary files
- Comprehensive logging
- Request validation with Pydantic
- Health check endpoint
- Optional callback URLs for async processing
- **Secure API Key Authentication**

## Security

### API Key Authentication

This API uses API key authentication to secure all endpoints (except health check). All requests must include a valid API key in the `X-API-Key` header.

#### Generate API Key

1. **Using the generator script:**
```bash
python generate_api_key.py
```

2. **Using the API endpoint (one-time setup):**
```bash
curl -X POST http://localhost:8000/generate-api-key
```

3. **Set the API key as environment variable:**
```bash
export API_KEY="your-generated-key-here"
```

4. **Or add to .env file:**
```env
API_KEY=your-generated-key-here
```

#### Using the API Key

Include the API key in all requests:

```bash
curl -X POST http://localhost:8000/merge-videos \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-generated-key-here" \
     -d '{"video_urls": ["http://..."], "output_filename": "merged.mp4"}'
```

#### Security Best Practices

- Store API keys securely (environment variables, key management systems)
- Do not commit API keys to version control
- Regenerate API keys periodically
- Use HTTPS in production
- Consider implementing rate limiting for additional security

## Requirements

- Python 3.8+
- MinIO server or AWS S3 access
- FFmpeg (for video processing)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd vi-upper
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install FFmpeg:
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt update && sudo apt install ffmpeg`
   - **Windows**: Download from https://ffmpeg.org/download.html

5. Create environment configuration:
```bash
cp .env.example .env
```

6. Edit `.env` file with your MinIO/S3 configuration:
```env
# MinIO/S3 Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# Bucket Configuration
SOURCE_BUCKET=source-videos
TARGET_BUCKET=merged-videos

# Domain Configuration (optional)
SUBDOMAIN=your-subdomain
DOMAIN_NAME=your-domain.com

# Optional: AWS S3 Configuration (if using AWS instead of MinIO)
# AWS_ACCESS_KEY_ID=your_aws_access_key
# AWS_SECRET_ACCESS_KEY=your_aws_secret_key
# AWS_REGION=us-east-1

# Application Configuration
TEMP_DIR=./temp
LOG_LEVEL=INFO

# YouTube API Configuration
YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json
YOUTUBE_TOKEN_FILE=token.json

# API Key for Video Merger API
# Generate using: python generate_api_key.py
API_KEY=your-generated-api-key-here
```

7. Set up YouTube Data API v3 (for YouTube upload feature):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable YouTube Data API v3
   - Create OAuth 2.0 Client ID credentials
   - Download the credentials as `client_secrets.json` in project root
   - The first API call will prompt for OAuth authorization

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | API key for authentication | Required |
| `MINIO_ENDPOINT` | MinIO server endpoint | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `MINIO_SECURE` | Use HTTPS for MinIO | `false` |
| `SOURCE_BUCKET` | Source bucket name | `source-videos` |
| `TARGET_BUCKET` | Target bucket name | `merged-videos` |
| `SUBDOMAIN` | Subdomain for domain configuration (optional) | - |
| `DOMAIN_NAME` | Domain name for domain configuration (optional) | - |
| `AWS_ACCESS_KEY_ID` | AWS access key (optional) | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (optional) | - |
| `AWS_REGION` | AWS region (optional) | `us-east-1` |
| `TEMP_DIR` | Temporary files directory | `./temp` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `YOUTUBE_CLIENT_SECRETS_FILE` | Path to YouTube OAuth credentials file | `client_secrets.json` |
| `YOUTUBE_TOKEN_FILE` | Path to YouTube token storage file | `token.json` |

## Usage

### Start the API server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

### API Endpoints

#### POST /merge-videos

Merge multiple videos from URLs into a single MP4 file.

**Request Body:**
```json
{
  "video_urls": [
    "http://localhost:9000/source-videos/video1.mp4",
    "http://localhost:9000/source-videos/video2.mp4",
    "http://localhost:9000/source-videos/video3.mp4"
  ],
  "output_filename": "my_merged_video.mp4"
}
```

**Response:**
```json
{
  "merged_video_url": "http://localhost:9000/merged-videos/my_merged_video.mp4",
  "filename": "my_merged_video.mp4",
  "processing_time_seconds": 15.45
}
```

#### POST /upload/youtube

Upload a video from MinIO to YouTube.

**Request Body:**
```json
{
  "video_url": "http://localhost:9000/source-videos/my-video.mp4",
  "title": "My YouTube Video Title",
  "description": "A brief description of the video",
  "tags": ["tag1", "tag2", "tag3"],
  "categoryId": "22",
  "privacyStatus": "public",
  "callback_url": "https://my-webhook.com/youtube-callback"
}
```

**Response:**
```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "video_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "status": "uploaded",
  "message": "Video uploaded successfully to YouTube",
  "error": null
}
```

#### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000000"
}
```

### Example Usage with curl

**Video Merge:**
```bash
curl -X POST "http://localhost:8000/merge-videos" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "video_urls": [
      "http://localhost:9000/source-videos/video1.mp4",
      "http://localhost:9000/source-videos/video2.mp4"
    ],
    "output_filename": "merged_result.mp4"
  }'
```

**YouTube Upload:**
```bash
curl -X POST "http://localhost:8000/upload/youtube" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "video_url": "http://localhost:9000/source-videos/my-video.mp4",
    "title": "My YouTube Video",
    "description": "Uploaded via API",
    "tags": ["api", "automation"],
    "privacyStatus": "unlisted"
  }'
```

### Example Usage with Python

**Video Merge:**
```python
import requests

url = "http://localhost:8000/merge-videos"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key-here"
}
payload = {
    "video_urls": [
        "http://localhost:9000/source-videos/video1.mp4",
        "http://localhost:9000/source-videos/video2.mp4"
    ],
    "output_filename": "my_merged_video.mp4"
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()
print(f"Merged video URL: {result['merged_video_url']}")
```

**YouTube Upload:**
```python
import requests

url = "http://localhost:8000/upload/youtube"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key-here"
}
payload = {
    "video_url": "http://localhost:9000/source-videos/my-video.mp4",
    "title": "My YouTube Video",
    "description": "Uploaded via API",
    "tags": ["api", "automation"],
    "privacyStatus": "unlisted"
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()
if result['success']:
    print(f"YouTube URL: {result['video_url']}")
```

### Example Clients

The project includes example client scripts:

- `python example_client.py` - Interactive demo for video merging
- `python youtube_example_client.py` - Interactive demo for YouTube uploads

## Development

### Development Server

```bash
# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Support (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t video-merger-api .
docker run -p 8000:8000 --env-file .env video-merger-api
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Make sure FFmpeg is installed and available in PATH
2. **MinIO connection error**: Verify MinIO server is running and credentials are correct
3. **Video format error**: Only MP4 files are supported
4. **Memory issues**: Large videos may require more system memory

### Logs

The application logs detailed information about the video processing pipeline. Check the console output for debugging information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.
