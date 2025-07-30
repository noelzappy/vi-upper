import os
import boto3
import requests
from minio import Minio
from minio.error import S3Error
from botocore.exceptions import ClientError
import logging
from typing import Optional
from urllib.parse import urlparse
from datetime import timedelta

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self):
        """Initialize S3 client with MinIO or AWS S3 configuration."""
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        self.minio_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        self.source_bucket = os.getenv("SOURCE_BUCKET", "source-videos")
        self.target_bucket = os.getenv("TARGET_BUCKET", "merged-videos")
        
        # Initialize clients
        self._init_minio_client()
        self._init_boto3_client()
        
        # Ensure target bucket exists
        self._ensure_bucket_exists(self.target_bucket)
    
    def _init_minio_client(self):
        """Initialize MinIO client."""
        if self.minio_endpoint and self.minio_access_key and self.minio_secret_key:
            try:
                self.minio_client = Minio(
                    self.minio_endpoint,
                    access_key=self.minio_access_key,
                    secret_key=self.minio_secret_key,
                    secure=self.minio_secure
                )
                logger.info(f"MinIO client initialized for endpoint: {self.minio_endpoint}")
            except Exception as e:
                logger.error(f"Failed to initialize MinIO client: {str(e)}")
                self.minio_client = None
        else:
            self.minio_client = None
            logger.warning("MinIO configuration not found")
    
    def _init_boto3_client(self):
        """Initialize boto3 client for AWS S3."""
        try:
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_region = os.getenv("AWS_REGION", "us-east-1")
            
            if aws_access_key and aws_secret_key:
                self.boto3_client = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
                logger.info("Boto3 S3 client initialized")
            else:
                self.boto3_client = None
                logger.info("AWS S3 configuration not found")
        except Exception as e:
            logger.error(f"Failed to initialize boto3 client: {str(e)}")
            self.boto3_client = None
    
    def _ensure_bucket_exists(self, bucket_name: str):
        """Ensure the bucket exists, create if it doesn't."""
        try:
            if self.minio_client:
                if not self.minio_client.bucket_exists(bucket_name):
                    self.minio_client.make_bucket(bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
                else:
                    logger.info(f"Bucket exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {str(e)}")
    
    async def download_video(self, url: str, temp_dir: str, filename: str) -> str:
        """
        Download video from URL to local temporary directory.
        
        Args:
            url: URL of the video to download
            temp_dir: Temporary directory to save the video
            filename: Name of the file to save
            
        Returns:
            Path to the downloaded file
        """
        file_path = os.path.join(temp_dir, filename)
        
        try:
            # Parse URL to determine if it's an S3 URL or direct HTTP URL
            parsed_url = urlparse(url)
            
            if self._is_s3_url(url):
                # Handle S3 URL
                await self._download_from_s3(url, file_path)
            else:
                # Handle direct HTTP URL
                await self._download_from_http(url, file_path)
            
            # Verify file was downloaded and has content
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                raise Exception(f"Downloaded file is empty or doesn't exist: {file_path}")
            
            logger.info(f"Successfully downloaded video to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to download video from {url}: {str(e)}")
            # Clean up partial download
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
    
    def _is_s3_url(self, url: str) -> bool:
        """Check if URL is an S3 URL."""
        parsed = urlparse(url)
        return parsed.hostname and ('amazonaws.com' in parsed.hostname or 
                                  parsed.hostname == self.minio_endpoint.split(':')[0])
    
    async def _download_from_s3(self, url: str, file_path: str):
        """Download file from S3."""
        # Extract bucket and key from S3 URL
        parsed = urlparse(url)
        
        if 'amazonaws.com' in parsed.hostname:
            # AWS S3 URL format
            path_parts = parsed.path.lstrip('/').split('/')
            bucket = path_parts[0]
            key = '/'.join(path_parts[1:])
            
            if self.boto3_client:
                self.boto3_client.download_file(bucket, key, file_path)
            else:
                raise Exception("AWS S3 client not configured")
        else:
            # MinIO URL format
            path_parts = parsed.path.lstrip('/').split('/')
            bucket = path_parts[0]
            key = '/'.join(path_parts[1:])
            
            if self.minio_client:
                self.minio_client.fget_object(bucket, key, file_path)
            else:
                raise Exception("MinIO client not configured")
    
    async def _download_from_http(self, url: str, file_path: str):
        """Download file from direct HTTP URL."""
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    
    async def upload_video(self, file_path: str, object_name: str) -> str:
        """
        Upload video to target bucket.
        
        Args:
            file_path: Local path to the video file
            object_name: Name of the object in the bucket
            
        Returns:
            URL of the uploaded video
        """
        try:
            if self.minio_client:
                # Upload to MinIO
                self.minio_client.fput_object(
                    self.target_bucket,
                    object_name,
                    file_path,
                    content_type='video/mp4'
                )
                
                # Generate presigned URL for access
                url = self.minio_client.presigned_get_object(
                    self.target_bucket,
                    object_name,
                    expires=timedelta(days=7)  # URL valid for 7 days
                )
                
                logger.info(f"Video uploaded to MinIO: {object_name}")
                return url
                
            elif self.boto3_client:
                # Upload to AWS S3
                self.boto3_client.upload_file(
                    file_path,
                    self.target_bucket,
                    object_name,
                    ExtraArgs={'ContentType': 'video/mp4'}
                )
                
                # Generate public URL
                aws_region = os.getenv("AWS_REGION", "us-east-1")
                url = f"https://{self.target_bucket}.s3.{aws_region}.amazonaws.com/{object_name}"
                
                logger.info(f"Video uploaded to AWS S3: {object_name}")
                return url
            else:
                raise Exception("No S3 client configured")
                
        except Exception as e:
            logger.error(f"Failed to upload video: {str(e)}")
            raise
