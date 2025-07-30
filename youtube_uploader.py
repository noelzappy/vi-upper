import os
import logging
import aiohttp
import aiofiles
import tempfile
from typing import List, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)


class YouTubeUploader:
    def __init__(self):
        """Initialize YouTube uploader with OAuth credentials."""
        self.credentials_file = os.getenv(
            "YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json"
        )
        self.token_file = os.getenv("YOUTUBE_TOKEN_FILE", "token.json")
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        self.api_service_name = "youtube"
        self.api_version = "v3"

    def _get_authenticated_service(self):
        """Get authenticated YouTube API service."""
        credentials = None

        # Load existing token
        if os.path.exists(self.token_file):
            try:
                credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.scopes
                )
            except Exception as e:
                logger.warning(f"Failed to load existing token: {e}")

        # If no valid credentials, get new ones
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    logger.info("Refreshed YouTube API credentials")
                except Exception as e:
                    logger.warning(f"Failed to refresh credentials: {e}")
                    credentials = None

            if not credentials:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"Client secrets file not found at {self.credentials_file}. "
                        "Please download from Google Cloud Console."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )

                credentials = flow.run_local_server(
                    port=0,
                )
                logger.info("Obtained new YouTube API credentials")

            # Save credentials
            try:
                with open(self.token_file, "w") as token:
                    token.write(credentials.to_json())
                logger.info("Saved YouTube API credentials")
            except Exception as e:
                logger.warning(f"Failed to save credentials: {e}")

        return build(self.api_service_name, self.api_version, credentials=credentials)

    async def download_video(self, video_url: str, output_path: str) -> str:
        """
        Download video from URL to local file.

        Args:
            video_url: URL of the video to download
            output_path: Local path to save the video

        Returns:
            Path to the downloaded file
        """
        try:
            logger.info(f"Downloading video from: {video_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as response:
                    response.raise_for_status()

                    # Get content length for progress tracking
                    content_length = response.headers.get("content-length")
                    if content_length:
                        total_size = int(content_length)
                        logger.info(f"Video size: {total_size / (1024 * 1024):.2f} MB")

                    # Download file
                    async with aiofiles.open(output_path, "wb") as file:
                        downloaded = 0
                        async for chunk in response.content.iter_chunked(8192):
                            await file.write(chunk)
                            downloaded += len(chunk)

                            if (
                                content_length and downloaded % (1024 * 1024) == 0
                            ):  # Log every MB
                                progress = (downloaded / total_size) * 100
                                logger.info(f"Download progress: {progress:.1f}%")

            # Verify file was downloaded
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception(
                    f"Downloaded file is empty or doesn't exist: {output_path}"
                )

            file_size = os.path.getsize(output_path)
            logger.info(
                f"Successfully downloaded video: {file_size / (1024 * 1024):.2f} MB"
            )

            return output_path

        except Exception as e:
            logger.error(f"Failed to download video from {video_url}: {str(e)}")
            # Clean up partial download
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = "22",
        privacy_status: str = "public",
    ) -> Dict[str, Any]:
        """
        Upload video to YouTube.

        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category ID
            privacy_status: Privacy status (public, unlisted, private)

        Returns:
            Dictionary with upload result information
        """
        try:
            logger.info(f"Starting YouTube upload for: {title}")

            # Get authenticated service
            youtube = self._get_authenticated_service()

            # Prepare video metadata
            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": category_id,
                },
                "status": {"privacyStatus": privacy_status},
            }

            # Create media upload object
            media = MediaFileUpload(
                video_path,
                chunksize=-1,  # Upload in a single request
                resumable=True,
            )

            # Execute upload
            logger.info("Uploading video to YouTube...")
            insert_request = youtube.videos().insert(
                part=",".join(body.keys()), body=body, media_body=media
            )

            # Execute the upload with retry logic
            response = None
            error = None
            retry = 0
            max_retries = 3

            while response is None and retry < max_retries:
                try:
                    status, response = insert_request.next_chunk()
                    if response is not None:
                        if "id" in response:
                            video_id = response["id"]
                            video_url = f"https://youtube.com/watch?v={video_id}"

                            logger.info(f"Video uploaded successfully: {video_url}")

                            return {
                                "success": True,
                                "video_id": video_id,
                                "video_url": video_url,
                                "status": "uploaded",
                                "message": "Video uploaded successfully to YouTube",
                            }
                        else:
                            logger.error(f"Upload failed with response: {response}")
                            return {
                                "success": False,
                                "error": "Upload failed - no video ID returned",
                                "response": response,
                            }
                    else:
                        if status:
                            progress = int(status.progress() * 100)
                            logger.info(f"Upload progress: {progress}%")

                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        # Retriable error
                        retry += 1
                        logger.warning(
                            f"Retriable error occurred, retry {retry}/{max_retries}: {e}"
                        )
                        if retry >= max_retries:
                            raise
                    else:
                        # Non-retriable error
                        logger.error(f"Non-retriable HTTP error: {e}")
                        raise
                except Exception as e:
                    logger.error(f"Unexpected error during upload: {e}")
                    raise

            # If we get here, upload failed
            return {
                "success": False,
                "error": "Upload failed after retries",
                "message": "Failed to upload video to YouTube after multiple attempts",
            }

        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {e}")
            return {
                "success": False,
                "error": "authentication_error",
                "message": str(e),
            }
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return {
                "success": False,
                "error": "youtube_api_error",
                "message": f"YouTube API error: {e.error_details}",
            }
        except Exception as e:
            logger.error(f"Unexpected error during YouTube upload: {e}")
            return {"success": False, "error": "upload_error", "message": str(e)}

    async def upload_video_from_url(
        self,
        video_url: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = "22",
        privacy_status: str = "public",
    ) -> Dict[str, Any]:
        """
        Download video from URL and upload to YouTube.

        Args:
            video_url: URL of the video to download
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category ID
            privacy_status: Privacy status

        Returns:
            Dictionary with upload result information
        """
        temp_file = None

        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                temp_file = tmp.name

            # Download video
            await self.download_video(video_url, temp_file)

            # Upload to YouTube
            result = self.upload_video(
                temp_file, title, description, tags, category_id, privacy_status
            )

            return result

        except Exception as e:
            logger.error(f"Failed to upload video from URL: {e}")
            return {"success": False, "error": "processing_error", "message": str(e)}

        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file: {e}")

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get information about an uploaded video.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with video information
        """
        try:
            youtube = self._get_authenticated_service()

            response = (
                youtube.videos()
                .list(part="snippet,status,statistics", id=video_id)
                .execute()
            )

            if response["items"]:
                video = response["items"][0]
                return {"success": True, "video_info": video}
            else:
                return {"success": False, "error": "Video not found"}

        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {"success": False, "error": str(e)}
