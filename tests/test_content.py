"""
Test content generation with Abacus.AI.
"""

import sys
import os
sys.path.append('../scripts')

# Load environment variables from parent directory
from dotenv import load_dotenv
load_dotenv('../.env')

from logger import initialize_logger
from generate_script import ContentGenerator

def test_content_generation():
    """Test content generation for Tech channel."""
    print("🤖 Testing Content Generation with Abacus.AI")
    print("=" * 50)
    
    try:
        # Initialize logger
        logger = initialize_logger()
        print("✅ Logger initialized")
        
        # Get API key
        abacus_api_key = os.getenv('ABACUS_API_KEY')
        if not abacus_api_key:
            print("❌ ABACUS_API_KEY not found in .env file")
            return False
        
        print(f"✅ API key found: {abacus_api_key[:10]}...")
        
        # Create content generator
        generator = ContentGenerator(abacus_api_key)
        print("✅ Content generator created")
        
        # Create channel config
        channel_config = {
            "channel_name": "Tech News",
            "channel_type": "tech_news",
            "voiceover": True,
            "topics": ["latest AI trends", "new gadgets", "big tech news"]
        }
        
        # Generate content
        print("\n📝 Generating script for 'latest AI trends'...")
        script = generator.generate_script(channel_config, 'latest AI trends')
        
        print("\n🎉 Generated Content:")
        print("=" * 30)
        print(f"Title: {script.get('title', 'No title')}")
        print(f"Description: {script.get('description', 'No description')}")
        print(f"Tags: {script.get('tags', 'No tags')}")
        print(f"Script: {script.get('script', 'No script')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Content generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_content_generation()
    
    if success:
        print("\n✅ Content generation test successful!")
    else:
        print("\n❌ Content generation test failed!")
