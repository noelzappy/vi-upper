#!/usr/bin/env python3
"""
Example script demonstrating how to use the YouTube Upload API endpoint.
"""

import requests
import json
import time
import sys

# API Configuration
API_BASE_URL = "http://localhost:8000"


def check_api_health():
    """Check if the API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy and running")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Make sure the API is running at http://localhost:8000")
        return False


def upload_to_youtube_example():
    """Example of uploading a video to YouTube using the API."""

    # Example video URL (replace with your actual MinIO URL)
    video_url = "http://localhost:9000/source-videos/sample-video.mp4"

    # Request payload
    payload = {
        "video_url": video_url,
        "title": "Test Video Upload via API",
        "description": "This is a test video uploaded using the Video Merger API's YouTube upload feature. Created automatically via the API.",
        "tags": ["api", "test", "automation", "video", "upload"],
        "categoryId": "22",  # People & Blogs
        "privacyStatus": "unlisted",  # Start with unlisted for testing
        "callback_url": "https://webhook.site/your-webhook-url",  # Optional callback
    }

    print("📺 Starting YouTube upload request...")
    print(f"🎬 Video URL: {video_url}")
    print(f"📝 Title: {payload['title']}")
    print(f"🏷️  Tags: {', '.join(payload['tags'])}")
    print(f"🔒 Privacy: {payload['privacyStatus']}")

    try:
        # Make the API request
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/upload/youtube",
            json=payload,
            timeout=600,  # 10 minutes timeout for video processing
        )

        if response.status_code == 200:
            result = response.json()
            end_time = time.time()

            print("✅ YouTube upload request completed!")
            print(f"📋 Success: {result.get('success')}")
            print(f"📄 Status: {result.get('status')}")
            print(f"💬 Message: {result.get('message')}")

            if result.get("success"):
                print(f"🆔 Video ID: {result.get('video_id')}")
                print(f"🔗 YouTube URL: {result.get('video_url')}")
                print(f"⏱️  Total request time: {end_time - start_time:.2f} seconds")
            else:
                print(f"❌ Error: {result.get('error')}")

            return result

        else:
            print(f"❌ YouTube upload failed: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error details: {error_detail}")
            except:
                print(f"Error response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print("❌ Request timed out. YouTube upload may take longer for large files.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None


def test_invalid_requests():
    """Test various invalid request scenarios."""
    print("\n🧪 Testing invalid request scenarios...")

    # Test with invalid privacy status
    print("\n1. Testing invalid privacy status...")
    payload = {
        "video_url": "http://localhost:9000/source-videos/sample-video.mp4",
        "title": "Test Video",
        "description": "Test description",
        "tags": ["test"],
        "privacyStatus": "invalid_status",
    }

    response = requests.post(f"{API_BASE_URL}/upload/youtube", json=payload)
    print(f"   Status: {response.status_code}")
    if response.status_code != 200:
        print(f"   Expected error: {response.json().get('detail', 'No detail')}")

    # Test with title too long
    print("\n2. Testing title too long...")
    payload = {
        "video_url": "http://localhost:9000/source-videos/sample-video.mp4",
        "title": "A" * 101,  # 101 characters (YouTube limit is 100)
        "description": "Test description",
        "tags": ["test"],
    }

    response = requests.post(f"{API_BASE_URL}/upload/youtube", json=payload)
    print(f"   Status: {response.status_code}")
    if response.status_code != 200:
        print(f"   Expected error: {response.json().get('detail', 'No detail')}")

    # Test with invalid URL
    print("\n3. Testing invalid video URL...")
    payload = {
        "video_url": "not-a-valid-url",
        "title": "Test Video",
        "description": "Test description",
        "tags": ["test"],
    }

    response = requests.post(f"{API_BASE_URL}/upload/youtube", json=payload)
    print(f"   Status: {response.status_code}")
    if response.status_code != 200:
        print(f"   Expected error: {response.json().get('detail', 'No detail')}")


def main():
    """Main function."""
    print("📺 YouTube Upload API Example Client")
    print("=" * 45)

    # Check API health
    if not check_api_health():
        sys.exit(1)

    print("\n⚠️  IMPORTANT SETUP REQUIREMENTS:")
    print("1. You need to set up YouTube Data API v3 credentials:")
    print("   - Go to Google Cloud Console")
    print("   - Enable YouTube Data API v3")
    print("   - Create OAuth 2.0 credentials")
    print("   - Download as 'client_secrets.json' in the project root")
    print("2. Make sure you have a video file in your MinIO bucket")
    print("3. The first run will open a browser for OAuth authorization")

    proceed = (
        input("\nDo you have the YouTube API credentials set up? (y/N): ")
        .lower()
        .strip()
    )

    if proceed != "y" and proceed != "yes":
        print("👋 Please set up YouTube API credentials first.")
        print("📖 See README.md for detailed setup instructions.")
        sys.exit(0)

    # Test invalid requests first
    test_invalid_requests()

    # Ask user if they want to proceed with actual upload
    print("\n" + "=" * 50)
    proceed = (
        input("\nDo you want to proceed with actual YouTube upload? (y/N): ")
        .lower()
        .strip()
    )

    if proceed == "y" or proceed == "yes":
        result = upload_to_youtube_example()
        if result and result.get("success"):
            print("\n🎉 YouTube upload completed successfully!")
            print(f"🔗 Watch your video at: {result.get('video_url')}")
        else:
            print("\n❌ YouTube upload failed. Check the API logs for more details.")
            sys.exit(1)
    else:
        print("👋 YouTube upload cancelled.")


if __name__ == "__main__":
    main()
