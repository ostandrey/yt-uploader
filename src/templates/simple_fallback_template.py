"""
Simple fallback template for YouTube automation.
Uses basic MoviePy functionality without complex features.
"""

import os
import time
from typing import Dict, List, Optional
from datetime import datetime

try:
    from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, TextClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from logger import get_logger

class SimpleFallbackTemplate:
    """Simple fallback template that always works."""
    
    def __init__(self):
        self.logger = get_logger()
    
    def create_video(self, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a simple video that always works."""
        start_time = time.time()
        
        try:
            if not MOVIEPY_AVAILABLE:
                self.logger.log_error("MoviePy not available")
                return None
            
            # Create output directory
            output_dir = f"storage/{channel_config.get('channel_name', 'tech_news').lower().replace(' ', '_')}/videos"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = os.path.join(output_dir, f"simple_video_{timestamp}.mp4")
            
            self.logger.log_info(f"Creating simple fallback video: {video_path}")
            
            # Create simple background
            background = ColorClip(size=(1920, 1080), color=(0, 50, 100), duration=10)
            
            # Create simple text
            try:
                text_clip = TextClip(
                    content.get("title", "Tech News"),
                    fontsize=60,
                    color='white',
                    method='caption',
                    size=(1600, 200),
                    align='center'
                )
                text_clip = text_clip.set_position(('center', 'center'))
                text_clip = text_clip.set_duration(10)
                
                # Combine background and text
                final_video = CompositeVideoClip([background, text_clip])
            except Exception as e:
                self.logger.log_warning(f"Text creation failed, using background only: {e}")
                final_video = background
            
            # Add audio if available
            if audio_path and os.path.exists(audio_path):
                try:
                    audio_clip = AudioFileClip(audio_path)
                    # Match audio duration to video
                    if audio_clip.duration > final_video.duration:
                        audio_clip = audio_clip.subclip(0, final_video.duration)
                    final_video = final_video.set_audio(audio_clip)
                    audio_clip.close()
                except Exception as e:
                    self.logger.log_warning(f"Audio addition failed: {e}")
            
            # Write video
            final_video.write_videofile(
                video_path,
                fps=24,
                codec='libx264',
                audio_codec='aac' if audio_path else None,
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                verbose=False,
                logger=None
            )
            
            # Clean up
            final_video.close()
            
            creation_time = time.time() - start_time
            self.logger.log_success(f"Simple video created in {creation_time:.2f}s: {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.log_error(f"Simple template creation failed: {e}")
            import traceback
            self.logger.log_error(f"Error details: {traceback.format_exc()}")
            return None

class SimpleFallbackTemplateManager:
    """Manager for simple fallback templates."""
    
    def __init__(self):
        self.logger = get_logger()
        self.templates = {
            'tech_news': SimpleFallbackTemplate()
        }
    
    def create_video(self, template_name: str, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a video using the simple fallback template."""
        try:
            if template_name not in self.templates:
                self.logger.log_error(f"Template '{template_name}' not found")
                return None
            
            template = self.templates[template_name]
            return template.create_video(content, visuals, channel_config, audio_path)
            
        except Exception as e:
            self.logger.log_error(f"Simple video creation failed: {e}")
            return None

