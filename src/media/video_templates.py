"""
Video templates system for YouTube automation project.
Creates professional-looking video templates with dynamic content.
"""

import os
import random
import io
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import tempfile
import requests
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip, VideoClip, TextClip
    from moviepy.video.fx import resize, fadein, fadeout
    from moviepy.video.tools.drawing import color_gradient
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

from logger import get_logger
from simple_video_template import SimpleVideoTemplate

class VideoTemplate:
    """Base class for video templates."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = get_logger()
    
    def create_video(self, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a video using this template."""
        raise NotImplementedError

class TechNewsTemplate(VideoTemplate):
    """Modern tech news template with dynamic text overlays and smooth transitions."""
    
    def __init__(self):
        super().__init__("tech_news", "Modern tech news template with dynamic overlays")
        self.template_colors = {
            'primary': (15, 52, 96),      # #0f3460 - Dark blue
            'secondary': (83, 52, 131),   # #533483 - Purple
            'accent': (114, 9, 183),      # #7209b7 - Bright purple
            'text': (255, 255, 255),      # White text
            'background': (26, 26, 46)    # #1a1a2e - Dark background
        }
    
    def create_video(self, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a tech news video with dynamic content."""
        try:
            # Create output directory
            output_dir = f"storage/{channel_config.get('channel_name', 'tech_news').lower().replace(' ', '_')}/videos"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = os.path.join(output_dir, f"video_{timestamp}.mp4")
            
            self.logger.log_info(f"Creating tech news video: {video_path}")
            
            # Split script into segments
            script_segments = self._split_script(content["script"])
            
            # Create video clips for each segment
            video_clips = []
            for i, segment in enumerate(script_segments):
                clip = self._create_segment_clip(segment, visuals, i, len(script_segments))
                if clip:
                    video_clips.append(clip)
            
            if not video_clips:
                self.logger.log_error("No video clips created")
                return None
            
            # Combine all clips with transitions
            final_video = self._combine_with_transitions(video_clips)
            
            # Add audio if available
            if audio_path and os.path.exists(audio_path):
                final_video = self._add_audio(final_video, audio_path)
            
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
            
            self.logger.log_success(f"Video created successfully: {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.log_error(f"Video template creation failed: {e}")
            import traceback
            self.logger.log_error(f"Error details: {traceback.format_exc()}")
            return None
    
    def _split_script(self, script: str) -> List[str]:
        """Split script into segments for different clips."""
        # Split by sentences and limit to reasonable number
        sentences = [s.strip() for s in script.split('.') if s.strip()]
        if not sentences:
            sentences = [script]
        
        # Group sentences into segments (2-3 sentences per segment)
        segments = []
        current_segment = ""
        
        for sentence in sentences[:6]:  # Limit to 6 segments max
            if len(current_segment) + len(sentence) < 150:  # Keep segments reasonable length
                current_segment += sentence + ". "
            else:
                if current_segment:
                    segments.append(current_segment.strip())
                current_segment = sentence + ". "
        
        if current_segment:
            segments.append(current_segment.strip())
        
        return segments[:5]  # Max 5 segments
    
    def _create_segment_clip(self, text: str, visuals: List[Dict], segment_index: int, total_segments: int):
        """Create a video clip for a single segment."""
        try:
            # Get background (image or gradient)
            background = self._create_background(visuals, segment_index)
            
            # Create text overlay
            text_overlay = self._create_text_overlay(text, segment_index, total_segments)
            
            # Create title overlay (for first segment)
            title_overlay = None
            if segment_index == 0:
                title_overlay = self._create_title_overlay()
            
            # Combine all elements - create a single composite image
            if text_overlay or title_overlay:
                # Create a single overlay that combines text and title
                combined_overlay = self._create_combined_overlay(text, segment_index, total_segments)
                if combined_overlay:
                    clips = [background, combined_overlay]
                else:
                    clips = [background]
            else:
                clips = [background]
            
            # Calculate duration based on text length (roughly 3-5 seconds per segment)
            duration = max(3, min(6, len(text) / 20))
            
            composite = CompositeVideoClip(clips).set_duration(duration)
            
            # Add fade effects
            if segment_index == 0:
                composite = composite.fadein(0.5)
            if segment_index == total_segments - 1:
                composite = composite.fadeout(0.5)
            
            return composite
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create segment clip: {e}")
            return None
    
    def _create_background(self, visuals: List[Dict], segment_index: int):
        """Create background for a segment."""
        try:
            # Try to use an image from visuals
            if visuals and segment_index < len(visuals):
                visual = visuals[segment_index]
                if 'url' in visual:
                    return self._create_image_background(visual['url'])
            
            # Fallback to gradient background
            return self._create_gradient_background(segment_index)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create background: {e}")
            return self._create_gradient_background(segment_index)
    
    def _create_image_background(self, image_url: str):
        """Create background from image URL."""
        try:
            # Download image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Load and process image
            image = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize to vertical format
            image = image.resize((1080, 1920), Image.Resampling.LANCZOS)
            
            # Add dark overlay for better text readability
            overlay = Image.new('RGBA', (1080, 1920), (0, 0, 0, 100))
            image_rgba = image.convert('RGBA')
            image_with_overlay = Image.alpha_composite(image_rgba, overlay)
            image = image_with_overlay.convert('RGB')  # Convert back to RGB
            
            # Convert to numpy array
            img_array = np.array(image)
            
            # Create video clip
            frames = []
            for _ in range(90):  # 3 seconds at 30fps
                frames.append(img_array)
            
            return VideoClip(lambda t: frames[int(t * 30) % len(frames)], duration=3)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create image background: {e}")
            return self._create_gradient_background(0)
    
    def _create_gradient_background(self, segment_index: int):
        """Create gradient background."""
        colors = [
            self.template_colors['primary'],
            self.template_colors['secondary'],
            self.template_colors['accent'],
            self.template_colors['background']
        ]
        
        color = colors[segment_index % len(colors)]
        return ColorClip(size=(1080, 1920), color=color, duration=3)
    
    def _create_text_overlay(self, text: str, segment_index: int, total_segments: int):
        """Create text overlay using PIL."""
        try:
            # Create text image with PIL - use RGB instead of RGBA
            img = Image.new('RGB', (1080, 1920), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Try to use a system font
            try:
                font = ImageFont.truetype("arial.ttf", 48)
            except:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48)
                except:
                    font = ImageFont.load_default()
            
            # Word wrap text
            words = text.split()
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + " " + word if current_line else word
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] < 1000:  # Width limit
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            # Draw text lines
            y_start = 600  # Start position
            line_height = 60
            
            for i, line in enumerate(lines[:6]):  # Max 6 lines
                y_pos = y_start + (i * line_height)
                
                # Draw text with outline for better readability
                for dx in [-2, -1, 0, 1, 2]:
                    for dy in [-2, -1, 0, 1, 2]:
                        if dx != 0 or dy != 0:
                            draw.text((540 + dx, y_pos + dy), line, 
                                    font=font, fill=(0, 0, 0), anchor="mm")
                
                # Draw main text
                draw.text((540, y_pos), line, 
                         font=font, fill=self.template_colors['text'], anchor="mm")
            
            # Convert to video clip
            img_array = np.array(img)
            frames = []
            for _ in range(90):  # 3 seconds at 30fps
                frames.append(img_array)
            
            return VideoClip(lambda t: frames[int(t * 30) % len(frames)], duration=3)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create text overlay: {e}")
            return None
    
    def _create_title_overlay(self):
        """Create title overlay for the first segment."""
        try:
            img = Image.new('RGB', (1080, 1920), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            try:
                title_font = ImageFont.truetype("arial.ttf", 72)
            except:
                try:
                    title_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 72)
                except:
                    title_font = ImageFont.load_default()
            
            # Draw title
            title_text = "TECH NEWS"
            draw.text((540, 200), title_text, 
                     font=title_font, fill=self.template_colors['accent'], anchor="mm")
            
            # Convert to video clip
            img_array = np.array(img)
            frames = []
            for _ in range(90):
                frames.append(img_array)
            
            return VideoClip(lambda t: frames[int(t * 30) % len(frames)], duration=3)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create title overlay: {e}")
            return None
    
    def _create_combined_overlay(self, text: str, segment_index: int, total_segments: int):
        """Create a combined overlay with text and title if needed."""
        try:
            # Create a transparent overlay
            img = Image.new('RGBA', (1080, 1920), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
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
                                    font=text_font, fill=(0, 0, 0, 200), anchor="mm")
                
                # Draw main text
                draw.text((540, y_pos), line, 
                         font=text_font, fill=self.template_colors['text'], anchor="mm")
            
            # Convert to video clip
            img_array = np.array(img)
            frames = []
            for _ in range(90):  # 3 seconds at 30fps
                frames.append(img_array)
            
            return VideoClip(lambda t: frames[int(t * 30) % len(frames)], duration=3)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to create combined overlay: {e}")
            return None
    
    def _combine_with_transitions(self, clips: List):
        """Combine clips with smooth transitions."""
        if len(clips) == 1:
            return clips[0]
        
        # Add crossfade transitions
        transitioned_clips = []
        for i, clip in enumerate(clips):
            if i == 0:
                # First clip - fade in
                transitioned_clips.append(clip.fadein(0.5))
            elif i == len(clips) - 1:
                # Last clip - fade out
                transitioned_clips.append(clip.fadeout(0.5))
            else:
                # Middle clips - fade in and out
                transitioned_clips.append(clip.fadein(0.3).fadeout(0.3))
        
        return concatenate_videoclips(transitioned_clips)
    
    def _add_audio(self, video, audio_path: str):
        """Add audio to video with proper synchronization."""
        try:
            audio_clip = AudioFileClip(audio_path)
            
            # Match audio duration to video duration
            if audio_clip.duration > video.duration:
                audio_clip = audio_clip.subclip(0, video.duration)
            elif audio_clip.duration < video.duration:
                # Loop audio if shorter
                loops_needed = int(video.duration / audio_clip.duration) + 1
                audio_clip = concatenate_videoclips([audio_clip] * loops_needed).subclip(0, video.duration)
            
            return video.set_audio(audio_clip)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to add audio: {e}")
            return video

class VideoTemplateManager:
    """Manages different video templates."""
    
    def __init__(self):
        self.templates = {
            'tech_news': SimpleVideoTemplate(),  # Use simple template to avoid color issues
            'default': SimpleVideoTemplate()  # Fallback
        }
        self.logger = get_logger()
    
    def get_template(self, template_name: str) -> VideoTemplate:
        """Get a video template by name."""
        return self.templates.get(template_name, self.templates['default'])
    
    def create_video(self, template_name: str, content: Dict, visuals: List[Dict], 
                    channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a video using the specified template."""
        template = self.get_template(template_name)
        return template.create_video(content, visuals, channel_config, audio_path)
