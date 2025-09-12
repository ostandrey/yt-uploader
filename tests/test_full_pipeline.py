"""
Test the complete automation pipeline for Tech channel.
This tests: content generation → visuals → video → upload
"""

import sys
import os
sys.path.append('../scripts')

# Load environment variables from parent directory
from dotenv import load_dotenv
load_dotenv('../.env')

from logger import initialize_logger
from main import YouTubeAutomationPipeline

def test_full_pipeline():
    """Test the complete automation pipeline."""
    print("🚀 Testing Full Automation Pipeline")
    print("=" * 50)
    
    try:
        # Initialize logger
        logger = initialize_logger()
        print("✅ Logger initialized")
        
        # Test full pipeline for Tech channel
        print("\n📺 Testing Tech Channel Pipeline...")
        
        # Change to parent directory to find config files
        original_dir = os.getcwd()
        os.chdir('..')
        
        try:
            automation = YouTubeAutomationPipeline('.env')
            
            print("🔄 Running channel automation...")
            result = automation.run_single_channel('tech_news', 'latest AI trends')
        finally:
            # Change back to original directory
            os.chdir(original_dir)
        
        print(f"\n📊 Pipeline Result: {result}")
        
        if result:
            print("✅ Full pipeline test successful!")
            return True
        else:
            print("❌ Full pipeline test failed!")
            return False
        
    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_full_pipeline()
    
    if success:
        print("\n🎉 SUCCESS! Full automation pipeline is working!")
        print("🔄 Ready to create automated videos")
    else:
        print("\n❌ Pipeline test failed!")
        print("🔧 Check the error messages above")
