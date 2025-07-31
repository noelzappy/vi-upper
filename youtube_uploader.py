import os
import logging
import aiohttp
import aiofiles
import tempfile
import json
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
                credentials = self._get_new_credentials()

            # Save credentials
            try:
                with open(self.token_file, "w") as token:
                    token.write(credentials.to_json())
                logger.info("Saved YouTube API credentials")
            except Exception as e:
                logger.warning(f"Failed to save credentials: {e}")

        return build(self.api_service_name, self.api_version, credentials=credentials)

    def _get_new_credentials(self):
        """Get new credentials using device flow for Docker/VPS compatibility."""
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(
                f"Client secrets file not found at {self.credentials_file}. "
                "Please download from Google Cloud Console and ensure it's configured "
                "as a Desktop Application (not Web Application)."
            )

        # Try device flow first (best for Docker/VPS)
        # try:
        #     return self._device_flow_auth()
        # except Exception as e:
        #     logger.warning(f"Device flow failed: {e}")

        # Fallback to manual flow
        try:
            return self._manual_flow_auth()
        except Exception as e:
            logger.error(f"Manual flow also failed: {e}")
            raise

    def _device_flow_auth(self):
        """Use device flow for authentication (best for Docker/VPS)."""
        logger.info("🐳 Starting Device Flow Authentication for Docker/VPS")
        logger.info("=" * 60)

        # Create flow from client secrets

        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_file, self.scopes
        )

        # Use device flow
        try:
            # This method handles the entire device flow
            credentials = flow.run_local_server(
                port=0,
            )
            logger.info("✅ Device flow authentication successful!")
            return credentials

        except Exception as e:
            # If run_console fails, try manual device flow
            logger.warning(f"run_console failed: {e}, trying manual device flow")
            return self._manual_device_flow(flow)

    def _manual_device_flow(self, flow):
        """Manual implementation of device flow if run_console doesn't work."""
        import urllib.parse
        import urllib.request
        import time

        # Load client config
        with open(self.credentials_file, "r") as f:
            client_config = json.load(f)

        client_id = client_config["installed"]["client_id"]

        # Step 1: Get device code
        device_code_url = "https://oauth2.googleapis.com/device/code"
        device_data = {"client_id": client_id, "scope": " ".join(self.scopes)}

        device_req = urllib.request.Request(
            device_code_url,
            data=urllib.parse.urlencode(device_data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(device_req) as response:
            device_response = json.loads(response.read().decode())

        # Display instructions
        logger.info(f"""
📋 AUTHENTICATION REQUIRED
{"=" * 60}

🌐 Open this URL in your browser:
   {device_response["verification_url"]}

🔑 Enter this code:
   {device_response["user_code"]}

⏳ Waiting for you to complete authentication...
   (Timeout in {device_response.get("expires_in", 1800) // 60} minutes)

""")

        # Step 2: Poll for token
        token_url = "https://oauth2.googleapis.com/token"
        poll_data = {
            "client_id": client_id,
            "client_secret": client_config["installed"]["client_secret"],
            "device_code": device_response["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

        interval = device_response.get("interval", 5)
        expires_in = device_response.get("expires_in", 1800)
        start_time = time.time()

        while time.time() - start_time < expires_in:
            time.sleep(interval)

            poll_req = urllib.request.Request(
                token_url,
                data=urllib.parse.urlencode(poll_data).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            try:
                with urllib.request.urlopen(poll_req) as response:
                    token_response = json.loads(response.read().decode())

                    # Create credentials object
                    credentials = Credentials(
                        token=token_response["access_token"],
                        refresh_token=token_response.get("refresh_token"),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=client_id,
                        client_secret=client_config["installed"]["client_secret"],
                        scopes=self.scopes,
                    )

                    logger.info("✅ Manual device flow authentication successful!")
                    return credentials

            except urllib.error.HTTPError as e:
                try:
                    error_response = json.loads(e.read().decode())
                    error_code = error_response.get("error")

                    if error_code == "authorization_pending":
                        print(".", end="", flush=True)
                        continue
                    elif error_code == "slow_down":
                        interval += 5
                        continue
                    elif error_code in ["expired_token", "access_denied"]:
                        raise Exception(f"Authorization failed: {error_code}")
                    else:
                        raise Exception(f"Error: {error_response}")
                except json.JSONDecodeError:
                    raise Exception(f"HTTP Error: {e}")

        raise Exception("Authentication timed out")

    def _manual_flow_auth(self):
        """Fallback manual flow for environments where device flow isn't available."""
        logger.info("🔧 Starting Manual Flow Authentication")
        logger.info("=" * 50)

        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_file, self.scopes
        )
        flow.redirect_uri = "http://localhost:8000/"

        # Generate auth URL
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

        logger.info(f"""
📋 MANUAL AUTHENTICATION REQUIRED
{"=" * 60}

🌐 Copy and paste this URL into your browser:

{auth_url}

📝 After logging in, Google will redirect you to a URL that starts with
   'http://localhost'. Copy the ENTIRE URL and paste it below.
   
   Example: http://localhost:8080/?code=4/ABCD...&scope=...

""")

        # Get the full redirect URL from user
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                redirect_url = input(
                    f"🔗 Paste the full redirect URL (attempt {attempt + 1}/{max_attempts}): "
                ).strip()

                if not redirect_url:
                    logger.warning("No URL entered. Please try again.")
                    continue

                # Extract code from URL
                if "code=" not in redirect_url:
                    logger.warning(
                        "No authorization code found in URL. Please ensure you copied the complete URL."
                    )
                    continue

                # Parse the code from URL
                from urllib.parse import urlparse, parse_qs

                parsed_url = urlparse(redirect_url)
                query_params = parse_qs(parsed_url.query)

                if "code" not in query_params:
                    logger.warning("No authorization code found in URL parameters.")
                    continue

                auth_code = query_params["code"][0]

                # Exchange code for token
                flow.fetch_token(code=auth_code)
                credentials = flow.credentials

                logger.info("✅ Manual flow authentication successful!")
                return credentials

            except KeyboardInterrupt:
                logger.info("Authentication cancelled by user")
                return None
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    raise

        raise Exception("Maximum authentication attempts reached")

    def _is_running_in_docker(self):
        """Check if running inside Docker container."""
        return (
            os.path.exists("/.dockerenv")
            or os.environ.get("DOCKER_CONTAINER") == "true"
        )

    def _is_interactive(self):
        """Check if running in interactive mode."""
        try:
            import sys

            return sys.stdin.isatty()
        except:
            return False

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
