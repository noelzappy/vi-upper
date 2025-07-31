#!/usr/bin/env python3
"""
Script to generate an API key for the Video Merger API.
Run this script to generate a secure API key for your application.
"""

import secrets
import base64
import hashlib
import os


def generate_api_key() -> str:
    """Generate a secure API key using base64 encoding."""
    # Generate 32 random bytes and encode as base64
    random_bytes = secrets.token_bytes(32)
    api_key = base64.b64encode(random_bytes).decode("utf-8")
    return api_key


def main():
    """Generate and display a new API key."""
    print("🔐 Video Merger API Key Generator")
    print("=" * 40)

    # Generate new API key
    api_key = generate_api_key()
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    print(f"\n✅ Generated new API key:")
    print(f"API Key: {api_key}")
    print(f"Key Hash (SHA256): {key_hash}")

    print(f"\n📝 Setup Instructions:")
    print(f"1. Set environment variable:")
    print(f"   export API_KEY='{api_key}'")
    print(f"\n2. Or add to .env file:")
    print(f"   API_KEY={api_key}")

    print(f"\n🚀 Usage Instructions:")
    print(f"Include this key in the 'X-API-Key' header for all API requests:")
    print(f"")
    print(f"curl -X POST http://localhost:8000/merge-videos \\")
    print(f"     -H 'Content-Type: application/json' \\")
    print(f"     -H 'X-API-Key: {api_key}' \\")
    print(f"     -d '{{\"video_urls\": [...]}}'")

    print(f"\n⚠️  Security Notes:")
    print(f"- Store this key securely")
    print(f"- Do not commit it to version control")
    print(f"- Use environment variables or secure key management")
    print(f"- Regenerate periodically for better security")

    # Check if .env file exists and offer to add the key
    if os.path.exists(".env"):
        response = input(f"\n❓ .env file found. Add API_KEY to .env file? (y/n): ")
        if response.lower() in ["y", "yes"]:
            with open(".env", "a") as f:
                f.write(f"\n# API Key for Video Merger API\n")
                f.write(f"API_KEY={api_key}\n")
            print(f"✅ API_KEY added to .env file")
    else:
        response = input(f"\n❓ Create .env file with API_KEY? (y/n): ")
        if response.lower() in ["y", "yes"]:
            with open(".env", "w") as f:
                f.write(f"# Video Merger API Configuration\n")
                f.write(f"API_KEY={api_key}\n")
            print(f"✅ .env file created with API_KEY")


if __name__ == "__main__":
    main()
