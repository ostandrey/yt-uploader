"""
Video assembly script for YouTube automation project.
Creates actual MP4 videos from content and visuals using MoviePy.
"""

import os
import random
import io
from typing import Dict, List, Optional
from datetime import datetime
import tempfile

try:
    from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, VideoClip
    from moviepy.video.fx import resize
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: MoviePy not installed. Install with: pip install moviepy")

from logger import get_logger

class VideoAssembler:
    def __init__(self):
        """Initialize the video assembler."""
        self.logger = get_logger()
        
        if not MOVIEPY_AVAILABLE:
            self.logger.log_error("MoviePy not available. Cannot create videos.")
            raise ImportError("MoviePy is required for video assembly")
    
    def create_video(self, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """
        Create a complete video from content and visuals.
        
        Args:
            content: Generated content (script, title, description, tags)
            visuals: List of visual content (images/videos)
            channel_config: Channel configuration
            audio_path: Path to audio file (optional)
            
        Returns:
            Path to created video file or None if failed
        """
        try:
            self.logger.log_info("Starting video assembly")
            
            # Create output directory
            channel_name = channel_config["channel_name"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_dir = f"storage/{channel_name.lower().replace(' ', '_')}/videos"
            os.makedirs(video_dir, exist_ok=True)
            
            video_filename = f"video_{timestamp}.mp4"
            video_path = os.path.join(video_dir, video_filename)
            
            # Create video components
            script = content.get("script", "")
            title = content.get("title", "Tech Update")
            
            # Create text clips for the script
            text_clips = self._create_text_clips(script, channel_config)
            
            # Create background clips from visuals
            background_clips = self._create_background_clips(visuals, len(text_clips))
            
            # Combine all clips
            final_video = self._combine_clips(text_clips, background_clips, channel_config)
            
            # Add audio if available
            if audio_path and os.path.exists(audio_path):
                try:
                    self.logger.log_info(f"Adding audio: {audio_path}")
                    # Use AudioFileClip instead of VideoFileClip for audio files
                    from moviepy.editor import AudioFileClip
                    audio_clip = AudioFileClip(audio_path)
                    
                    # Match audio duration to video duration
                    if audio_clip.duration > final_video.duration:
                        audio_clip = audio_clip.subclip(0, final_video.duration)
                    elif audio_clip.duration < final_video.duration:
                        # Loop audio if it's shorter than video
                        loops_needed = int(final_video.duration / audio_clip.duration) + 1
                        audio_clip = concatenate_videoclips([audio_clip] * loops_needed).subclip(0, final_video.duration)
                    
                    final_video = final_video.set_audio(audio_clip)
                    self.logger.log_success("Audio successfully added to video")
                except Exception as e:
                    self.logger.log_warning(f"Failed to add audio: {e}")
                    import traceback
                    self.logger.log_warning(f"Audio error details: {traceback.format_exc()}")
            
            # Write video file
            self.logger.log_info(f"Writing video to: {video_path}")
            final_video.write_videofile(
                video_path,
                fps=24,
                codec='libx264',
                audio_codec='aac' if audio_path else None,
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
            
            # Clean up
            final_video.close()
            for clip in text_clips + background_clips:
                clip.close()
            
            self.logger.log_success(f"Video created successfully: {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.log_error(f"Video assembly failed: {e}")
            return None
    
    def _create_text_clips(self, script: str, channel_config: Dict) -> List:
        """Create text clips from the script (simplified without ImageMagick)."""
        try:
            # For now, we'll create simple color clips instead of text clips
            # This avoids the ImageMagick dependency issue
            sentences = [s.strip() for s in script.split('.') if s.strip()]
            if not sentences:
                sentences = [script]
            
            # Create simple color clips for each sentence
            text_clips = []
            for i, sentence in enumerate(sentences[:5]):  # Limit to 5 clips
                # Create a simple colored clip instead of text
                # We'll use different colors to represent different parts
                # Convert hex colors to RGB tuples
                colors = [
                    (255, 107, 107),  # #FF6B6B
                    (78, 205, 196),   # #4ECDC4
                    (69, 183, 209),   # #45B7D1
                    (150, 206, 180),  # #96CEB4
                    (255, 234, 167)   # #FFEAA7
                ]
                color = colors[i % len(colors)]
                
                clip = ColorClip(size=(1080, 1920), color=color, duration=3)
                text_clips.append(clip)
            
            return text_clips
            
        except Exception as e:
            self.logger.log_error(f"Failed to create text clips: {e}")
            return []
    
    def _create_background_clips(self, visuals: List[Dict], num_clips: int) -> List:
        """Create background clips from visual content."""
        try:
            background_clips = []
            
            # If no visuals, create solid color backgrounds
            if not visuals:
                colors = [
                    (26, 26, 46),    # #1a1a2e
                    (22, 33, 62),    # #16213e
                    (15, 52, 96),    # #0f3460
                    (83, 52, 131),   # #533483
                    (114, 9, 183)    # #7209b7
                ]
                for i in range(num_clips):
                    color = random.choice(colors)
                    clip = ColorClip(size=(1080, 1920), color=color, duration=3)
                    background_clips.append(clip)
                return background_clips
            
            # Use available visuals
            for i in range(num_clips):
                if i < len(visuals):
                    visual = visuals[i]
                    if isinstance(visual, dict) and 'url' in visual:
                        try:
                            # Download and use the image
                            clip = self._create_clip_from_url(visual['url'], duration=3)
                            if clip:
                                background_clips.append(clip)
                            else:
                                # Fallback to solid color
                                background_clips.append(self._create_solid_background())
                        except:
                            background_clips.append(self._create_solid_background())
                    else:
                        background_clips.append(self._create_solid_background())
                else:
                    background_clips.append(self._create_solid_background())
            
            return background_clips
            
        except Exception as e:
            self.logger.log_error(f"Failed to create background clips: {e}")
            return []
    
    def _create_clip_from_url(self, url: str, duration: int = 3):
        """Create a video clip from an image URL."""
        try:
            import requests
            from PIL import Image
            import tempfile
            import numpy as np
            
            # Download image
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Load image with PIL
            image = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize to vertical format (1080x1920)
            image = image.resize((1080, 1920), Image.Resampling.LANCZOS)
            
            # Convert to numpy array
            img_array = np.array(image)
            
            # Create a video clip from the image array
            # We'll create multiple frames to make it a proper video clip
            frames = []
            for _ in range(int(duration * 30)):  # 30 fps
                frames.append(img_array)
            
            # Convert to video clip
            clip = VideoClip(lambda t: frames[int(t * 30) % len(frames)], duration=duration)
            
            return clip
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create clip from URL {url}: {e}")
            return None
    
    def _create_solid_background(self, duration: int = 3):
        """Create a solid color background clip."""
        colors = [
            (26, 26, 46),    # #1a1a2e
            (22, 33, 62),    # #16213e
            (15, 52, 96),    # #0f3460
            (83, 52, 131),   # #533483
            (114, 9, 183)    # #7209b7
        ]
        color = random.choice(colors)
        return ColorClip(size=(1080, 1920), color=color, duration=duration)
    
    def _combine_clips(self, text_clips: List, background_clips: List, channel_config: Dict):
        """Combine text and background clips into final video."""
        try:
            if not text_clips or not background_clips:
                # Create a simple video with just text
                if text_clips:
                    return CompositeVideoClip([text_clips[0]])
                else:
                    return self._create_solid_background(duration=10)
            
            # Ensure we have the same number of clips
            min_clips = min(len(text_clips), len(background_clips))
            
            # Create composite clips
            composite_clips = []
            for i in range(min_clips):
                # Use only the background clips (images) for now
                # We'll add text overlays later when we have proper text rendering
                composite = CompositeVideoClip([
                    background_clips[i]
                ])
                composite_clips.append(composite)
            
            # Concatenate all clips
            if len(composite_clips) > 1:
                final_video = concatenate_videoclips(composite_clips)
            else:
                final_video = composite_clips[0]
            
            return final_video
            
        except Exception as e:
            self.logger.log_error(f"Failed to combine clips: {e}")
            # Return a simple fallback video
            return self._create_solid_background(duration=10)

# Example usage
if __name__ == "__main__":
    # Test the video assembler
    from logger import initialize_logger
    initialize_logger()
    
    assembler = VideoAssembler()
    
    # Test content
    test_content = {
        "script": "The latest AI trends are revolutionizing technology! From ChatGPT to autonomous vehicles, AI is everywhere.",
        "title": "Latest AI Trends 2025",
        "description": "Discover the latest AI trends and innovations!",
        "tags": ["AI", "Technology", "Innovation"]
    }
    
    test_visuals = []
    test_config = {"channel_name": "Tech News"}
    
    video_path = assembler.create_video(test_content, test_visuals, test_config)
    if video_path:
        print(f"Test video created: {video_path}")
    else:
        print("Test video creation failed")
