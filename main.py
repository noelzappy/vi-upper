from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from pydantic import BaseModel, HttpUrl
from typing import List, Annotated
import os
import tempfile
import shutil
import uuid
import logging
import aiohttp
import secrets
import base64
import hashlib
from datetime import datetime
from dotenv import load_dotenv

from video_merger import VideoMerger
from s3_client import S3Client
from youtube_uploader import YouTubeUploader

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video Merger API",
    description="API for merging videos from MinIO S3 buckets",
    version="1.0.0",
)


# API Key Authentication Functions
def generate_api_key() -> str:
    """Generate a secure API key using base64 encoding."""
    # Generate 32 random bytes and encode as base64
    random_bytes = secrets.token_bytes(32)
    api_key = base64.b64encode(random_bytes).decode("utf-8")
    return api_key


def get_api_key_hash() -> str:
    """Get the expected API key hash from environment."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        # Generate a new API key if none exists
        new_key = generate_api_key()
        logger.warning(f"No API_KEY found in environment. Generated new key: {new_key}")
        logger.warning(
            "Please set API_KEY environment variable with this key for production use."
        )
        return hashlib.sha256(new_key.encode()).hexdigest()

    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(x_api_key: Annotated[str, Header()]) -> bool:
    """Verify the provided API key against the expected hash."""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required. Provide it in the 'X-API-Key' header.",
        )

    # Hash the provided key and compare
    provided_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    expected_hash = get_api_key_hash()

    if provided_hash != expected_hash:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    return True


# Get the expected API key hash at startup
expected_api_key_hash = get_api_key_hash()


class VideoMergeRequest(BaseModel):
    video_urls: List[HttpUrl]
    output_filename: str | None = None


class VideoMergeResponse(BaseModel):
    merged_video_url: str
    filename: str
    processing_time_seconds: float


class YouTubeUploadRequest(BaseModel):
    video_url: HttpUrl
    title: str
    description: str
    tags: List[str]
    categoryId: str = "22"  # Default: People & Blogs
    privacyStatus: str = "public"  # public | unlisted | private
    callback_url: str | None = None


class YouTubeUploadResponse(BaseModel):
    success: bool
    video_id: str | None = None
    video_url: str | None = None
    status: str
    message: str
    error: str | None = None


# Initialize clients
s3_client = S3Client()
video_merger = VideoMerger()
youtube_uploader = YouTubeUploader()


@app.get("/")
async def root():
    return {"message": "Video Merger API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# @app.post("/generate-api-key")
# async def generate_new_api_key():
#     """
#     Generate a new API key. This endpoint is unprotected for initial setup.
#     In production, you should remove this endpoint or protect it with admin credentials.
#     """
#     new_key = generate_api_key()
#     key_hash = hashlib.sha256(new_key.encode()).hexdigest()

#     return {
#         "api_key": new_key,
#         "key_hash": key_hash,
#         "instructions": {
#             "setup": "Set the API_KEY environment variable to this key value",
#             "usage": "Include this key in the 'X-API-Key' header for all requests",
#             "security": "Store this key securely and do not share it",
#         },
#     }


@app.post("/merge-videos", response_model=VideoMergeResponse)
async def merge_videos(
    request: VideoMergeRequest, api_key_valid: bool = Depends(verify_api_key)
):
    """
    Merge multiple videos from URLs into a single MP4 file.

    Args:
        request: VideoMergeRequest containing list of video URLs

    Returns:
        VideoMergeResponse with the URL of the merged video
    """
    start_time = datetime.utcnow()
    temp_dir = None

    try:
        logger.info(
            f"Starting video merge process for {len(request.video_urls)} videos"
        )

        # Validate input
        if not request.video_urls:
            raise HTTPException(status_code=400, detail="No video URLs provided")

        if len(request.video_urls) < 2:
            raise HTTPException(
                status_code=400, detail="At least 2 videos are required for merging"
            )

        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="video_merge_")
        logger.info(f"Created temporary directory: {temp_dir}")

        # Download videos
        logger.info("Downloading videos...")
        downloaded_files = []
        for i, url in enumerate(request.video_urls):
            try:
                file_path = await s3_client.download_video(
                    str(url), temp_dir, f"video_{i}.mp4"
                )
                downloaded_files.append(file_path)
                logger.info(f"Downloaded video {i + 1}/{len(request.video_urls)}")
            except Exception as e:
                logger.error(f"Failed to download video from {url}: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download video from {url}: {str(e)}",
                )

        # Generate output filename
        if not request.output_filename:
            output_filename = f"merged_video_{uuid.uuid4().hex[:8]}_{int(datetime.utcnow().timestamp())}.mp4"
        else:
            output_filename = request.output_filename
            if not output_filename.endswith(".mp4"):
                output_filename += ".mp4"

        # Merge videos
        logger.info("Merging videos...")
        merged_video_path = os.path.join(temp_dir, output_filename)
        await video_merger.merge_videos(downloaded_files, merged_video_path)
        logger.info("Videos merged successfully")

        # Upload merged video
        logger.info("Uploading merged video...")
        merged_video_url = await s3_client.upload_video(
            merged_video_path, output_filename
        )
        logger.info(f"Merged video uploaded: {merged_video_url}")

        # Clean up downloaded files
        for file in downloaded_files:
            try:
                os.remove(file)
                logger.info(f"Removed temporary file: {file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {file}: {str(e)}")

        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        logger.info(f"Video merge process completed in {processing_time:.2f} seconds")

        return VideoMergeResponse(
            merged_video_url=merged_video_url,
            filename=output_filename,
            processing_time_seconds=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during video merge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    finally:
        # Clean up temporary files
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temporary directory {temp_dir}: {str(e)}"
                )


@app.post("/upload/youtube", response_model=YouTubeUploadResponse)
async def upload_to_youtube(
    request: YouTubeUploadRequest, api_key_valid: bool = Depends(verify_api_key)
):
    """
    Download video from URL and upload to YouTube.

    Args:
        request: YouTubeUploadRequest containing video URL and metadata

    Returns:
        YouTubeUploadResponse with upload result
    """
    start_time = datetime.utcnow()

    try:
        logger.info(f"Starting YouTube upload for video: {request.title}")
        logger.info(f"Video URL: {request.video_url}")

        # Validate privacy status
        valid_privacy_statuses = ["public", "unlisted", "private"]
        if request.privacyStatus not in valid_privacy_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid privacy status. Must be one of: {valid_privacy_statuses}",
            )

        # Validate title length (YouTube limit is 100 characters)
        if len(request.title) > 100:
            raise HTTPException(
                status_code=400, detail="Title must be 100 characters or less"
            )

        # Validate description length (YouTube limit is 5000 characters)
        if len(request.description) > 5000:
            raise HTTPException(
                status_code=400, detail="Description must be 5000 characters or less"
            )

        # Validate tags (YouTube allows up to 500 characters total)
        total_tags_length = sum(len(tag) for tag in request.tags)
        if total_tags_length > 500:
            raise HTTPException(
                status_code=400,
                detail="Total length of all tags must be 500 characters or less",
            )

        # Upload video to YouTube
        result = await youtube_uploader.upload_video_from_url(
            video_url=str(request.video_url),
            title=request.title,
            description=request.description,
            tags=request.tags,
            category_id=request.categoryId,
            privacy_status=request.privacyStatus,
        )

        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        logger.info(
            f"YouTube upload process completed in {processing_time:.2f} seconds"
        )

        # Send callback if provided
        if request.callback_url and result.get("success"):
            try:
                callback_data = {
                    "video_id": result.get("video_id"),
                    "video_url": result.get("video_url"),
                    "status": result.get("status"),
                    "processing_time_seconds": processing_time,
                    "title": request.title,
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        request.callback_url,
                        json=callback_data,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            logger.info(
                                f"Callback sent successfully to {request.callback_url}"
                            )
                        else:
                            logger.warning(
                                f"Callback failed with status {response.status}"
                            )
            except Exception as e:
                logger.warning(f"Failed to send callback: {str(e)}")

        # Return response
        if result.get("success"):
            return YouTubeUploadResponse(
                success=True,
                video_id=result.get("video_id"),
                video_url=result.get("video_url"),
                status=result.get("status", "uploaded"),
                message=result.get("message", "Video uploaded successfully to YouTube"),
            )
        else:
            return YouTubeUploadResponse(
                success=False,
                status="failed",
                message=result.get("message", "Failed to upload video to YouTube"),
                error=result.get("error"),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during YouTube upload: {str(e)}")
        return YouTubeUploadResponse(
            success=False,
            status="error",
            message=f"Internal server error: {str(e)}",
            error="internal_error",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
