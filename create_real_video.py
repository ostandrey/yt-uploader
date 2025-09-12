"""
Create a real video file using MoviePy for YouTube Shorts.
This demonstrates the complete video assembly process.
"""

import os
import sys
from datetime import datetime

# Add scripts to path
sys.path.append('scripts')

from logger import initialize_logger
from generate_script import ContentGenerator
from get_visuals import VisualContentFetcher

def create_real_video():
    """Create a real video file using MoviePy."""
    print("🎬 Creating Real Video with MoviePy")
    print("=" * 40)
    
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
        
        # Generate content
        print("\n📝 Generating content...")
        channel_config = {
            "channel_name": "Tech News",
            "channel_type": "tech_news",
            "voiceover": True,
            "topics": ["latest AI trends", "new gadgets", "big tech news"]
        }
        
        topic = "latest AI trends"
        content = content_generator.generate_script(channel_config, topic)
        print(f"✅ Content generated: {content.get('title', 'No title')[:50]}...")
        
        # Get visuals (with placeholders if needed)
        visuals = visual_fetcher.get_visuals_for_script(content, channel_config, count=3)
        if len(visuals) == 0:
            print("   ⚠️ Creating placeholder visuals...")
            visuals = [
                {"type": "image", "title": "AI Visual 1", "url": "placeholder1.jpg"},
                {"type": "image", "title": "AI Visual 2", "url": "placeholder2.jpg"},
                {"type": "image", "title": "AI Visual 3", "url": "placeholder3.jpg"}
            ]
        print(f"✅ Visuals ready: {len(visuals)} items")
        
        # Create video using MoviePy
        print("\n🎬 Creating video with MoviePy...")
        
        try:
            from moviepy.editor import *
            print("✅ MoviePy imported successfully")
            
            # Create a simple video with text and background
            # For YouTube Shorts: 1080x1920 (9:16 aspect ratio)
            
            # Create text clip
            title_text = content.get('title', 'Tech News Update')[:50] + "..."
            txt_clip = TextClip(
                title_text,
                fontsize=50,
                color='white',
                font='Arial-Bold',
                size=(1000, 200)
            ).set_position('center').set_duration(3)
            
            # Create background (solid color)
            background = ColorClip(size=(1080, 1920), color=(0, 100, 200)).set_duration(5)
            
            # Create script text
            script_text = content.get('script', 'Tech news update')[:200] + "..."
            script_clip = TextClip(
                script_text,
                fontsize=30,
                color='white',
                font='Arial',
                size=(1000, 400),
                method='caption'
            ).set_position(('center', 300)).set_duration(5)
            
            # Composite the video
            video = CompositeVideoClip([
                background,
                txt_clip.set_start(0),
                script_clip.set_start(1)
            ])
            
            # Create output filename
            video_filename = f"tech_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            video_path = f"storage/tech_news/{video_filename}"
            
            # Create storage directory
            os.makedirs("storage/tech_news", exist_ok=True)
            
            # Write video file
            print(f"   📹 Rendering video: {video_path}")
            video.write_videofile(
                video_path,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
            
            # Get file size
            file_size = os.path.getsize(video_path)
            file_size_mb = file_size / (1024 * 1024)
            
            print(f"✅ Video created successfully!")
            print(f"   📁 File: {video_path}")
            print(f"   📊 Size: {file_size_mb:.2f} MB")
            print(f"   ⏱️ Duration: 5 seconds")
            print(f"   📐 Resolution: 1080x1920 (Shorts format)")
            
            # Clean up
            video.close()
            
            return video_path
            
        except ImportError:
            print("❌ MoviePy not installed")
            print("🔧 Install with: pip install moviepy")
            return None
            
    except Exception as e:
        print(f"❌ Video creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    video_path = create_real_video()
    
    if video_path:
        print(f"\n🎉 SUCCESS! Real video created: {video_path}")
        print("📺 This is a real MP4 file ready for YouTube upload!")
    else:
        print("\n❌ Video creation failed!")
        print("🔧 Check the error messages above")
