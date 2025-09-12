"""
Test only the Tech channel pipeline without initializing other channels.
"""

import sys
import os
sys.path.append('../scripts')

# Load environment variables from parent directory
from dotenv import load_dotenv
load_dotenv('../.env')

from logger import initialize_logger
from generate_script import ContentGenerator
from get_visuals import VisualContentFetcher
from upload_youtube import YouTubeUploader

def test_tech_channel_only():
    """Test only the Tech channel components."""
    print("🚀 Testing Tech Channel Only")
    print("=" * 40)
    
    try:
        # Initialize logger
        logger = initialize_logger()
        print("✅ Logger initialized")
        
        # Change to parent directory to find config files
        original_dir = os.getcwd()
        os.chdir('..')
        
        try:
            # Initialize components individually for Tech channel only
            print("\n📝 Initializing content generator...")
            content_generator = ContentGenerator(
                abacus_api_key=os.getenv('ABACUS_API_KEY'),
                openai_api_key=os.getenv('OPENAI_API_KEY')
            )
            print("✅ Content generator initialized")
            
            print("\n🖼️ Initializing visual fetcher...")
            visual_fetcher = VisualContentFetcher(
                pexels_api_key=os.getenv('PEXELS_API_KEY'),
                pixabay_api_key=os.getenv('PIXABAY_API_KEY'),
                unsplash_access_key=os.getenv('UNSPLASH_ACCESS_KEY'),
                abacus_api_key=os.getenv('ABACUS_API_KEY')
            )
            print("✅ Visual fetcher initialized")
            
            print("\n📺 Initializing YouTube uploader for Tech channel...")
            youtube_uploader = YouTubeUploader(
                channel_name="Tech Daily Updates",
                credentials_file="credentials/tech_credentials.json",
                token_file="tokens/tech_token.json"
            )
            print("✅ YouTube uploader initialized")
            
            # Test content generation
            print("\n📝 Testing content generation...")
            channel_config = {
                "channel_name": "Tech News",
                "channel_type": "tech_news",
                "voiceover": True,
                "topics": ["latest AI trends", "new gadgets", "big tech news"]
            }
            
            content = content_generator.generate_script(channel_config, 'latest AI trends')
            print("✅ Content generated successfully")
            print(f"   Title: {content.get('title', 'No title')[:50]}...")
            
            # Test visual fetching
            print("\n🖼️ Testing visual fetching...")
            visuals = visual_fetcher.get_visuals_for_script(content, channel_config)
            print(f"✅ Visuals fetched: {len(visuals)} items")
            
            print("\n🎉 Tech channel pipeline test successful!")
            return True
            
        finally:
            # Change back to original directory
            os.chdir(original_dir)
        
    except Exception as e:
        print(f"❌ Tech channel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tech_channel_only()
    
    if success:
        print("\n✅ SUCCESS! Tech channel pipeline is working!")
        print("🔄 Ready to create automated videos for Tech channel")
    else:
        print("\n❌ Tech channel test failed!")
        print("🔧 Check the error messages above")
