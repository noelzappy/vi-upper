# Video Merger API

A FastAPI application for merging videos stored in MinIO S3 buckets.

## Features

- Download videos from MinIO S3 buckets via URLs
- Merge multiple MP4 videos into a single video file
- Upload the merged video to a target S3 bucket
- Support for both MinIO and AWS S3
- Automatic cleanup of temporary files
- Comprehensive logging
- Request validation with Pydantic
- Health check endpoint

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
# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# Bucket Configuration
SOURCE_BUCKET=source-videos
TARGET_BUCKET=merged-videos

# Application Configuration
TEMP_DIR=./temp
LOG_LEVEL=INFO
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MINIO_ENDPOINT` | MinIO server endpoint | `localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | `minioadmin` |
| `MINIO_SECURE` | Use HTTPS for MinIO | `false` |
| `SOURCE_BUCKET` | Source bucket name | `source-videos` |
| `TARGET_BUCKET` | Target bucket name | `merged-videos` |
| `AWS_ACCESS_KEY_ID` | AWS access key (optional) | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (optional) | - |
| `AWS_REGION` | AWS region (optional) | `us-east-1` |
| `TEMP_DIR` | Temporary files directory | `./temp` |
| `LOG_LEVEL` | Logging level | `INFO` |

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

```bash
curl -X POST "http://localhost:8000/merge-videos" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "http://localhost:9000/source-videos/video1.mp4",
      "http://localhost:9000/source-videos/video2.mp4"
    ],
    "output_filename": "merged_result.mp4"
  }'
```

### Example Usage with Python

```python
import requests

url = "http://localhost:8000/merge-videos"
payload = {
    "video_urls": [
        "http://localhost:9000/source-videos/video1.mp4",
        "http://localhost:9000/source-videos/video2.mp4"
    ],
    "output_filename": "my_merged_video.mp4"
}

response = requests.post(url, json=payload)
result = response.json()
print(f"Merged video URL: {result['merged_video_url']}")
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

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
