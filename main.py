from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List
import os
import tempfile
import shutil
import uuid
import logging
from datetime import datetime
from dotenv import load_dotenv

from video_merger import VideoMerger
from s3_client import S3Client

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


class VideoMergeRequest(BaseModel):
    video_urls: List[HttpUrl]
    output_filename: str | None = None


class VideoMergeResponse(BaseModel):
    merged_video_url: str
    filename: str
    processing_time_seconds: float


# Initialize clients
s3_client = S3Client()

video_merger = VideoMerger()


@app.get("/")
async def root():
    return {"message": "Video Merger API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/merge-videos", response_model=VideoMergeResponse)
async def merge_videos(request: VideoMergeRequest):
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
