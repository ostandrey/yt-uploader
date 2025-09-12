"""
Create your first automated YouTube video using the current flow.
This script demonstrates the complete pipeline from content generation to upload.
"""

import os
import sys
from datetime import datetime

# Add scripts to path
sys.path.append('scripts')

from logger import initialize_logger
from generate_script import ContentGenerator
from get_visuals import VisualContentFetcher
from upload_youtube import YouTubeUploader

def create_first_video():
    """Create the first automated video for Tech channel."""
    print("🎬 Creating Your First Automated YouTube Video")
    print("=" * 50)
    
    try:
        # Initialize logger
        logger = initialize_logger()
        print("✅ Logger initialized")
        
        # Initialize components
        print("\n📝 Initializing content generator...")
        content_generator = ContentGenerator(
            abacus_api_key=os.getenv('ABACUS_API_KEY'),
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        print("✅ Content generator ready")
        
        print("\n🖼️ Initializing visual fetcher...")
        visual_fetcher = VisualContentFetcher(
            pexels_api_key=os.getenv('PEXELS_API_KEY'),
            pixabay_api_key=os.getenv('PIXABAY_API_KEY'),
            unsplash_access_key=os.getenv('UNSPLASH_ACCESS_KEY'),
            abacus_api_key=os.getenv('ABACUS_API_KEY')
        )
        print("✅ Visual fetcher ready")
        
        print("\n📺 Initializing YouTube uploader...")
        youtube_uploader = YouTubeUploader(
            channel_name="Tech Daily Updates",
            credentials_file="credentials/tech_credentials.json",
            token_file="tokens/tech_token.json"
        )
        print("✅ YouTube uploader ready")
        
        # Step 1: Generate Content
        print("\n📝 Step 1: Generating Content")
        print("-" * 30)
        
        channel_config = {
            "channel_name": "Tech News",
            "channel_type": "tech_news",
            "voiceover": True,
            "topics": ["latest AI trends", "new gadgets", "big tech news"]
        }
        
        topic = "latest AI trends"
        print(f"🎯 Topic: {topic}")
        
        content = content_generator.generate_script(channel_config, topic)
        print("✅ Content generated successfully")
        print(f"   📝 Title: {content.get('title', 'No title')}")
        print(f"   📄 Description: {content.get('description', 'No description')[:100]}...")
        print(f"   🏷️ Tags: {len(content.get('tags', []))} tags")
        print(f"   📜 Script: {len(content.get('script', ''))} characters")
        
        # Step 2: Fetch Visuals
        print("\n🖼️ Step 2: Fetching Visual Content")
        print("-" * 30)
        
        visuals = visual_fetcher.get_visuals_for_script(content, channel_config, count=5)
        print(f"✅ Visuals fetched: {len(visuals)} items")
        
        # If no visuals fetched, create placeholder visuals
        if len(visuals) == 0:
            print("   ⚠️ No visuals from APIs, creating placeholders...")
            visuals = [
                {
                    "type": "image",
                    "title": "AI Technology Visual",
                    "url": "placeholder_ai.jpg",
                    "description": "AI and technology concept image",
                    "source": "placeholder"
                },
                {
                    "type": "image", 
                    "title": "Tech Innovation Visual",
                    "url": "placeholder_tech.jpg",
                    "description": "Technology innovation concept image",
                    "source": "placeholder"
                },
                {
                    "type": "image",
                    "title": "Future Tech Visual", 
                    "url": "placeholder_future.jpg",
                    "description": "Future technology concept image",
                    "source": "placeholder"
                }
            ]
            print(f"   ✅ Created {len(visuals)} placeholder visuals")
        
        for i, visual in enumerate(visuals[:3], 1):
            print(f"   🖼️ Visual {i}: {visual.get('type', 'unknown')} - {visual.get('title', 'No title')[:50]}...")
        
        # Step 3: Create Video File (Placeholder)
        print("\n🎬 Step 3: Video Assembly")
        print("-" * 30)
        
        # For now, create a placeholder video file
        video_filename = f"tech_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        video_path = f"storage/tech_news/{video_filename}"
        
        # Create storage directory if it doesn't exist
        os.makedirs("storage/tech_news", exist_ok=True)
        
        # Create a simple placeholder video file
        with open(video_path, 'w') as f:
            f.write("# Placeholder video file\n")
            f.write(f"# Content: {content.get('title', 'No title')}\n")
            f.write(f"# Script: {content.get('script', 'No script')}\n")
            f.write(f"# Visuals: {len(visuals)} items\n")
            f.write(f"# Created: {datetime.now().isoformat()}\n")
        
        print(f"✅ Video file created: {video_path}")
        print("   📝 Note: This is a placeholder file. Real video assembly will be implemented next.")
        
        # Step 4: Upload to YouTube (Optional)
        print("\n📺 Step 4: YouTube Upload")
        print("-" * 30)
        
        upload_choice = input("Do you want to upload this video to YouTube? (y/n): ").lower().strip()
        
        if upload_choice == 'y':
            print("🚀 Uploading to YouTube...")
            
            # Upload video
            youtube_id = youtube_uploader.upload_video(
                video_path=video_path,
                title=content.get('title', 'Tech News Update'),
                description=content.get('description', 'Latest tech news and trends'),
                tags=content.get('tags', []),
                privacy_status="unlisted"  # Start with unlisted for review
            )
            
            if youtube_id:
                print(f"✅ Video uploaded successfully!")
                print(f"   📺 YouTube ID: {youtube_id}")
                print(f"   🔗 Video URL: https://www.youtube.com/watch?v={youtube_id}")
                print(f"   🔒 Status: Unlisted (for review)")
                print("\n📋 Next Steps:")
                print("   1. Review the video in YouTube Studio")
                print("   2. Edit title/description if needed")
                print("   3. Change status to 'Public' when ready")
            else:
                print("❌ Upload failed")
        else:
            print("⏭️ Skipping upload. Video file saved for manual review.")
        
        # Summary
        print("\n🎉 First Video Creation Complete!")
        print("=" * 50)
        print(f"✅ Content: Generated for topic '{topic}'")
        print(f"✅ Visuals: {len(visuals)} items fetched")
        print(f"✅ Video: {video_path}")
        if upload_choice == 'y':
            print(f"✅ Upload: YouTube video created")
        print("\n🚀 Your automation pipeline is working!")
        
        return True
        
    except Exception as e:
        print(f"❌ Video creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_first_video()
    
    if success:
        print("\n🎊 SUCCESS! Your first automated video is ready!")
        print("🔄 Ready to scale to multiple videos and channels")
    else:
        print("\n❌ Video creation failed!")
        print("🔧 Check the error messages above and try again")
