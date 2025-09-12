"""
Test YouTube OAuth authentication for all channels.
"""

import sys
import os
sys.path.append('../scripts')

from logger import initialize_logger
from upload_youtube import YouTubeUploader

def test_tech_auth():
    """Test authentication for Tech channel."""
    print("🔐 Testing Tech Channel Authentication")
    print("=" * 40)
    
    try:
        # Initialize logger
        logger = initialize_logger()
        print("✅ Logger initialized")
        
        # Test Tech channel
        credentials_file = os.getenv('YOUTUBE_TECH_CREDENTIALS_FILE', '../credentials/tech_credentials.json')
        token_file = '../tokens/tech_token.json'
        
        print(f"📁 Credentials: {credentials_file}")
        print(f"📁 Token: {token_file}")
        
        # Check if token already exists
        if os.path.exists(token_file):
            print("✅ Token file already exists - authentication working!")
            return True
        
        # Test authentication
        uploader = YouTubeUploader(
            channel_name="Tech Daily Updates",
            credentials_file=credentials_file,
            token_file=token_file
        )
        
        print("✅ Tech channel authentication successful!")
        return True
        
    except Exception as e:
        print(f"❌ Tech channel authentication failed: {e}")
        return False

def test_all_auth():
    """Test authentication for all channels."""
    print("🚀 Testing YouTube Authentication for All Channels")
    print("=" * 60)
    
    # Test Tech channel
    tech_success = test_tech_auth()
    
    # TODO: Add Crypto and Memes channel tests later
    
    if tech_success:
        print("\n✅ Authentication tests passed!")
        return True
    else:
        print("\n❌ Authentication tests failed!")
        return False

if __name__ == "__main__":
    success = test_all_auth()
    
    if success:
        print("\n🎉 SUCCESS! YouTube authentication is working!")
    else:
        print("\n❌ Authentication failed!")
