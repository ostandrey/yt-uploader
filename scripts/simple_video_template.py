"""
Simple video template that avoids color format issues.
Creates professional videos with text overlays using a simpler approach.
"""

import os
import random
import io
from typing import Dict, List, Optional
from datetime import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, VideoClip
    from moviepy.video.fx import fadein, fadeout
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from logger import get_logger

class SimpleVideoTemplate:
    """Simple video template that creates videos by drawing text directly on images."""
    
    def __init__(self):
        self.logger = get_logger()
        self.template_colors = {
            'primary': (15, 52, 96),      # #0f3460 - Dark blue
            'secondary': (83, 52, 131),   # #533483 - Purple
            'accent': (114, 9, 183),      # #7209b7 - Bright purple
            'text': (255, 255, 255),      # White text
            'background': (26, 26, 46)    # #1a1a2e - Dark background
        }
    
    def create_video(self, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a simple video with text overlays."""
        try:
            # Create output directory
            output_dir = f"storage/{channel_config.get('channel_name', 'tech_news').lower().replace(' ', '_')}/videos"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = os.path.join(output_dir, f"video_{timestamp}.mp4")
            
            self.logger.log_info(f"Creating simple video: {video_path}")
            
            # Split script into segments
            script_segments = self._split_script(content["script"])
            
            # Create video clips for each segment
            video_clips = []
            for i, segment in enumerate(script_segments):
                clip = self._create_segment_with_text(segment, visuals, i, len(script_segments))
                if clip:
                    video_clips.append(clip)
            
            if not video_clips:
                self.logger.log_error("No video clips created")
                return None
            
            # Combine all clips
            if len(video_clips) > 1:
                final_video = concatenate_videoclips(video_clips)
            else:
                final_video = video_clips[0]
            
            # Add audio if available
            if audio_path and os.path.exists(audio_path):
                final_video = self._add_audio(final_video, audio_path)
            
            # Write video file with higher quality settings
            self.logger.log_info(f"Writing video to: {video_path}")
            final_video.write_videofile(
                video_path,
                fps=30,  # Higher FPS for smoother video
                codec='libx264',
                audio_codec='aac' if audio_path else None,
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                bitrate="5000k",  # Higher bitrate for better quality
                preset='medium'   # Better compression
            )
            
            self.logger.log_success(f"Video created successfully: {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.log_error(f"Simple video creation failed: {e}")
            import traceback
            self.logger.log_error(f"Error details: {traceback.format_exc()}")
            return None
    
    def _split_script(self, script: str) -> List[str]:
        """Split script into segments for different clips."""
        sentences = [s.strip() for s in script.split('.') if s.strip()]
        if not sentences:
            sentences = [script]
        
        # Group sentences into segments
        segments = []
        current_segment = ""
        
        for sentence in sentences[:6]:  # Limit to 6 segments max
            if len(current_segment) + len(sentence) < 150:
                current_segment += sentence + ". "
            else:
                if current_segment:
                    segments.append(current_segment.strip())
                current_segment = sentence + ". "
        
        if current_segment:
            segments.append(current_segment.strip())
        
        return segments[:5]  # Max 5 segments
    
    def _create_segment_with_text(self, text: str, visuals: List[Dict], segment_index: int, total_segments: int):
        """Create a video segment with text drawn directly on the image."""
        try:
            # Get background image
            background_image = self._get_background_image(visuals, segment_index)
            
            # Draw text directly on the image
            final_image = self._draw_text_on_image(background_image, text, segment_index, total_segments)
            
            # Convert to video clip
            img_array = np.array(final_image)
            frames = []
            duration = max(3, min(6, len(text) / 20))  # 3-6 seconds based on text length
            
            for _ in range(int(duration * 30)):  # 30 fps
                frames.append(img_array)
            
            clip = VideoClip(lambda t: frames[int(t * 30) % len(frames)], duration=duration)
            
            # Add fade effects
            if segment_index == 0:
                clip = clip.fadein(0.5)
            if segment_index == total_segments - 1:
                clip = clip.fadeout(0.5)
            
            return clip
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create segment: {e}")
            return None
    
    def _get_background_image(self, visuals: List[Dict], segment_index: int) -> Image.Image:
        """Get background image from visuals or create a gradient."""
        try:
            # Try to use an image from visuals
            if visuals and segment_index < len(visuals):
                visual = visuals[segment_index]
                if 'url' in visual:
                    return self._download_image(visual['url'])
            
            # Fallback to gradient background
            return self._create_gradient_image(segment_index)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to get background image: {e}")
            return self._create_gradient_image(segment_index)
    
    def _download_image(self, image_url: str) -> Image.Image:
        """Download and process image from URL."""
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            image = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize to vertical format
            image = image.resize((1080, 1920), Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            self.logger.log_warning(f"Failed to download image: {e}")
            return self._create_gradient_image(0)
    
    def _create_gradient_image(self, segment_index: int) -> Image.Image:
        """Create a gradient background image."""
        colors = [
            self.template_colors['primary'],
            self.template_colors['secondary'],
            self.template_colors['accent'],
            self.template_colors['background']
        ]
        
        color = colors[segment_index % len(colors)]
        return Image.new('RGB', (1080, 1920), color)
    
    def _draw_text_on_image(self, image: Image.Image, text: str, segment_index: int, total_segments: int) -> Image.Image:
        """Draw text directly on the image."""
        try:
            # Create a copy of the image to draw on
            img_with_text = image.copy()
            draw = ImageDraw.Draw(img_with_text)
            
            # Try to use system fonts
            try:
                title_font = ImageFont.truetype("arial.ttf", 72)
                text_font = ImageFont.truetype("arial.ttf", 48)
            except:
                try:
                    title_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 72)
                    text_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48)
                except:
                    title_font = ImageFont.load_default()
                    text_font = ImageFont.load_default()
            
            # Add title for first segment
            if segment_index == 0:
                title_text = "TECH NEWS"
                # Draw title with outline
                for dx in [-3, -2, -1, 0, 1, 2, 3]:
                    for dy in [-3, -2, -1, 0, 1, 2, 3]:
                        if dx != 0 or dy != 0:
                            draw.text((540 + dx, 200 + dy), title_text, 
                                    font=title_font, fill=(0, 0, 0), anchor="mm")
                
                draw.text((540, 200), title_text, 
                         font=title_font, fill=self.template_colors['accent'], anchor="mm")
            
            # Add main text
            words = text.split()
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + " " + word if current_line else word
                bbox = draw.textbbox((0, 0), test_line, font=text_font)
                if bbox[2] - bbox[0] < 1000:  # Width limit
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            # Draw text lines
            y_start = 600 if segment_index == 0 else 400  # Adjust for title
            line_height = 60
            
            for i, line in enumerate(lines[:6]):  # Max 6 lines
                y_pos = y_start + (i * line_height)
                
                # Draw text with outline for better readability
                for dx in [-2, -1, 0, 1, 2]:
                    for dy in [-2, -1, 0, 1, 2]:
                        if dx != 0 or dy != 0:
                            draw.text((540 + dx, y_pos + dy), line, 
                                    font=text_font, fill=(0, 0, 0), anchor="mm")
                
                # Draw main text
                draw.text((540, y_pos), line, 
                         font=text_font, fill=self.template_colors['text'], anchor="mm")
            
            return img_with_text
            
        except Exception as e:
            self.logger.log_warning(f"Failed to draw text on image: {e}")
            return image
    
    def _add_audio(self, video, audio_path: str):
        """Add audio to video with proper synchronization."""
        try:
            audio_clip = AudioFileClip(audio_path)
            
            # Use audio duration to determine video duration for better sync
            if audio_clip.duration > 0:
                # Adjust video to match audio duration
                if video.duration != audio_clip.duration:
                    # Stretch or compress video to match audio
                    speed_factor = video.duration / audio_clip.duration
                    if speed_factor > 0.5 and speed_factor < 2.0:  # Reasonable range
                        video = video.fx(lambda clip: clip.speedx(speed_factor))
                    else:
                        # If speed change is too extreme, just match durations
                        if audio_clip.duration > video.duration:
                            audio_clip = audio_clip.subclip(0, video.duration)
                        else:
                            # Extend video to match audio
                            video = video.loop(duration=audio_clip.duration)
            
            return video.set_audio(audio_clip)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to add audio: {e}")
            return video
