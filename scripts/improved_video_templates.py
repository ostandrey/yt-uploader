"""
Improved video templates system with better design, error handling, and performance.
Focuses on creating high-quality tech content videos.
"""

import os
import random
import io
import time
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

class ImprovedTechTemplate:
    """Improved tech news template with modern design and better performance."""
    
    def __init__(self):
        self.logger = get_logger()
        self.template_colors = {
            'primary': (0, 123, 255),        # #007bff - Modern blue
            'secondary': (40, 167, 69),      # #28a745 - Success green
            'accent': (255, 193, 7),         # #ffc107 - Warning yellow
            'text': (255, 255, 255),         # White text
            'text_dark': (33, 37, 41),       # #212529 - Dark text
            'background': (248, 249, 250),   # #f8f9fa - Light background
            'card': (255, 255, 255),         # White cards
            'border': (222, 226, 230)        # #dee2e6 - Light border
        }
        
        # Performance settings
        self.video_settings = {
            'fps': 30,
            'duration_per_segment': 4.0,
            'transition_duration': 0.5,
            'text_display_duration': 3.5
        }
    
    def create_video(self, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create an improved tech news video with modern design."""
        start_time = time.time()
        
        try:
            # Validate inputs
            if not self._validate_inputs(content, visuals, channel_config):
                return None
            
            # Create output directory
            output_dir = f"storage/{channel_config.get('channel_name', 'tech_news').lower().replace(' ', '_')}/videos"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = os.path.join(output_dir, f"tech_video_{timestamp}.mp4")
            
            self.logger.log_info(f"Creating improved tech video: {video_path}")
            
            # Split script into optimized segments
            script_segments = self._split_script_optimized(content["script"])
            
            # Create video clips with error handling
            video_clips = []
            for i, segment in enumerate(script_segments):
                try:
                    clip = self._create_modern_segment_clip(segment, visuals, i, len(script_segments))
                    if clip:
                        video_clips.append(clip)
                        self.logger.log_info(f"Created segment {i+1}/{len(script_segments)}")
                    else:
                        self.logger.log_warning(f"Failed to create segment {i+1}, skipping")
                except Exception as e:
                    self.logger.log_error(f"Error creating segment {i+1}: {e}")
                    continue
            
            if not video_clips:
                self.logger.log_error("No video clips created successfully")
                return None
            
            # Combine clips with smooth transitions
            final_video = self._combine_with_modern_transitions(video_clips)
            
            # Add audio with proper synchronization
            if audio_path and os.path.exists(audio_path):
                final_video = self._add_audio_optimized(final_video, audio_path)
            
            # Write video with optimized settings
            self.logger.log_info(f"Writing video to: {video_path}")
            final_video.write_videofile(
                video_path,
                fps=self.video_settings['fps'],
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
            self.logger.log_success(f"Video created successfully in {creation_time:.2f}s: {video_path}")
            return video_path
            
        except Exception as e:
            self.logger.log_error(f"Video template creation failed: {e}")
            import traceback
            self.logger.log_error(f"Error details: {traceback.format_exc()}")
            return None
    
    def _validate_inputs(self, content: Dict, visuals: List[Dict], channel_config: Dict) -> bool:
        """Validate input parameters."""
        try:
            if not content or not content.get("script"):
                self.logger.log_error("No script content provided")
                return False
            
            if not channel_config:
                self.logger.log_error("No channel configuration provided")
                return False
            
            if not MOVIEPY_AVAILABLE:
                self.logger.log_error("MoviePy not available")
                return False
            
            return True
        except Exception as e:
            self.logger.log_error(f"Input validation failed: {e}")
            return False
    
    def _split_script_optimized(self, script: str) -> List[str]:
        """Split script into optimized segments for better pacing."""
        try:
            # Clean and split script
            sentences = [s.strip() for s in script.split('.') if s.strip()]
            if not sentences:
                sentences = [script]
            
            # Create segments with optimal length for video pacing
            segments = []
            current_segment = ""
            target_length = 120  # Target characters per segment
            
            for sentence in sentences[:8]:  # Limit to 8 segments max
                if len(current_segment) + len(sentence) < target_length:
                    current_segment += sentence + ". "
                else:
                    if current_segment:
                        segments.append(current_segment.strip())
                    current_segment = sentence + ". "
            
            if current_segment:
                segments.append(current_segment.strip())
            
            # Ensure we have at least one segment
            if not segments:
                segments = [script[:200] + "..." if len(script) > 200 else script]
            
            self.logger.log_info(f"Split script into {len(segments)} segments")
            return segments[:6]  # Max 6 segments for optimal video length
            
        except Exception as e:
            self.logger.log_error(f"Script splitting failed: {e}")
            return [script[:200] + "..." if len(script) > 200 else script]
    
    def _create_modern_segment_clip(self, text: str, visuals: List[Dict], segment_index: int, total_segments: int):
        """Create a modern video clip with improved design."""
        try:
            # Create modern background
            background = self._create_modern_background(visuals, segment_index)
            
            # Create modern text overlay
            text_overlay = self._create_modern_text_overlay(text, segment_index, total_segments)
            
            # Create title overlay for first segment
            title_overlay = None
            if segment_index == 0:
                title_overlay = self._create_modern_title_overlay()
            
            # Combine elements
            clips = [background]
            if text_overlay:
                clips.append(text_overlay)
            if title_overlay:
                clips.append(title_overlay)
            
            # Create composite clip
            composite = CompositeVideoClip(clips, size=(1920, 1080))
            
            # Set duration
            composite = composite.set_duration(self.video_settings['duration_per_segment'])
            
            return composite
            
        except Exception as e:
            self.logger.log_error(f"Failed to create segment clip: {e}")
            return None
    
    def _create_modern_background(self, visuals: List[Dict], segment_index: int):
        """Create a modern background with gradient and visual elements."""
        try:
            # Try to use a visual if available
            if visuals and segment_index < len(visuals):
                visual = visuals[segment_index]
                if visual.get('image_path') and os.path.exists(visual['image_path']):
                    try:
                        # Load and resize image
                        img_clip = VideoFileClip(visual['image_path'])
                        img_clip = img_clip.resize((1920, 1080))
                        img_clip = img_clip.set_duration(self.video_settings['duration_per_segment'])
                        
                        # Add subtle overlay for text readability
                        overlay = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=self.video_settings['duration_per_segment'])
                        overlay = overlay.set_opacity(0.3)
                        
                        return CompositeVideoClip([img_clip, overlay])
                    except Exception as e:
                        self.logger.log_warning(f"Failed to use visual {segment_index}: {e}")
            
            # Fallback to modern gradient background
            return self._create_gradient_background(segment_index)
            
        except Exception as e:
            self.logger.log_error(f"Background creation failed: {e}")
            return self._create_gradient_background(segment_index)
    
    def _create_gradient_background(self, segment_index: int):
        """Create a modern gradient background."""
        try:
            # Create gradient colors based on segment
            colors = [
                (self.template_colors['primary'], self.template_colors['secondary']),
                (self.template_colors['secondary'], self.template_colors['accent']),
                (self.template_colors['accent'], self.template_colors['primary']),
                (self.template_colors['primary'], self.template_colors['accent']),
                (self.template_colors['secondary'], self.template_colors['primary']),
                (self.template_colors['accent'], self.template_colors['secondary'])
            ]
            
            color_pair = colors[segment_index % len(colors)]
            
            # Create gradient background
            background = ColorClip(size=(1920, 1080), color=color_pair[0], duration=self.video_settings['duration_per_segment'])
            
            # Add subtle pattern overlay
            pattern = self._create_pattern_overlay()
            if pattern:
                background = CompositeVideoClip([background, pattern])
            
            return background
            
        except Exception as e:
            self.logger.log_error(f"Gradient background creation failed: {e}")
            # Ultimate fallback
            return ColorClip(size=(1920, 1080), color=self.template_colors['primary'], duration=self.video_settings['duration_per_segment'])
    
    def _create_pattern_overlay(self):
        """Create a subtle pattern overlay for visual interest."""
        try:
            # Create a subtle geometric pattern
            pattern = ColorClip(size=(1920, 1080), color=(255, 255, 255), duration=self.video_settings['duration_per_segment'])
            pattern = pattern.set_opacity(0.05)
            return pattern
        except:
            return None
    
    def _create_modern_text_overlay(self, text: str, segment_index: int, total_segments: int):
        """Create modern text overlay with better typography."""
        try:
            # Clean and format text
            clean_text = text.replace('\n', ' ').strip()
            if len(clean_text) > 200:
                clean_text = clean_text[:200] + "..."
            
            # Create text clip with modern styling
            text_clip = TextClip(
                clean_text,
                fontsize=48,
                color=self.template_colors['text'],
                font='Arial-Bold',
                method='caption',
                size=(1600, 400),
                align='center'
            )
            
            # Position text
            text_clip = text_clip.set_position(('center', 'center'))
            text_clip = text_clip.set_duration(self.video_settings['text_display_duration'])
            
            # Add subtle background for readability
            text_bg = ColorClip(size=(1700, 500), color=(0, 0, 0), duration=self.video_settings['text_display_duration'])
            text_bg = text_bg.set_opacity(0.7)
            text_bg = text_bg.set_position(('center', 'center'))
            
            # Combine text and background
            return CompositeVideoClip([text_bg, text_clip])
            
        except Exception as e:
            self.logger.log_error(f"Text overlay creation failed: {e}")
            return None
    
    def _create_modern_title_overlay(self):
        """Create modern title overlay for the first segment."""
        try:
            title_text = "TECH NEWS"
            
            # Create title clip
            title_clip = TextClip(
                title_text,
                fontsize=72,
                color=self.template_colors['text'],
                font='Arial-Bold',
                method='caption',
                size=(800, 100),
                align='center'
            )
            
            # Position at top
            title_clip = title_clip.set_position(('center', 100))
            title_clip = title_clip.set_duration(self.video_settings['duration_per_segment'])
            
            # Add background
            title_bg = ColorClip(size=(900, 120), color=self.template_colors['primary'], duration=self.video_settings['duration_per_segment'])
            title_bg = title_bg.set_position(('center', 90))
            
            return CompositeVideoClip([title_bg, title_clip])
            
        except Exception as e:
            self.logger.log_error(f"Title overlay creation failed: {e}")
            return None
    
    def _combine_with_modern_transitions(self, video_clips: List[VideoClip]):
        """Combine video clips with smooth modern transitions."""
        try:
            if not video_clips:
                return None
            
            if len(video_clips) == 1:
                return video_clips[0]
            
            # Add fade transitions between clips
            transitioned_clips = []
            for i, clip in enumerate(video_clips):
                if i == 0:
                    # First clip: fade in
                    clip = clip.fadein(self.video_settings['transition_duration'])
                elif i == len(video_clips) - 1:
                    # Last clip: fade out
                    clip = clip.fadeout(self.video_settings['transition_duration'])
                else:
                    # Middle clips: fade in and out
                    clip = clip.fadein(self.video_settings['transition_duration']).fadeout(self.video_settings['transition_duration'])
                
                transitioned_clips.append(clip)
            
            # Concatenate with crossfade
            final_video = concatenate_videoclips(transitioned_clips, method="compose")
            
            return final_video
            
        except Exception as e:
            self.logger.log_error(f"Video combination failed: {e}")
            return video_clips[0] if video_clips else None
    
    def _add_audio_optimized(self, video_clip: VideoClip, audio_path: str):
        """Add audio with proper synchronization and optimization."""
        try:
            # Load audio
            audio_clip = AudioFileClip(audio_path)
            
            # Match audio duration to video duration
            video_duration = video_clip.duration
            audio_duration = audio_clip.duration
            
            if audio_duration > video_duration:
                # Trim audio to match video
                audio_clip = audio_clip.subclip(0, video_duration)
            elif audio_duration < video_duration:
                # Loop audio to match video
                loops_needed = int(video_duration / audio_duration) + 1
                audio_clip = concatenate_videoclips([audio_clip] * loops_needed)
                audio_clip = audio_clip.subclip(0, video_duration)
            
            # Set audio to video
            final_video = video_clip.set_audio(audio_clip)
            
            # Clean up
            audio_clip.close()
            
            return final_video
            
        except Exception as e:
            self.logger.log_error(f"Audio addition failed: {e}")
            return video_clip

class ImprovedVideoTemplateManager:
    """Manager for improved video templates."""
    
    def __init__(self):
        self.logger = get_logger()
        self.templates = {
            'tech_news': ImprovedTechTemplate()
        }
    
    def create_video(self, template_name: str, content: Dict, visuals: List[Dict], channel_config: Dict, audio_path: Optional[str] = None) -> Optional[str]:
        """Create a video using the specified template."""
        try:
            if template_name not in self.templates:
                self.logger.log_error(f"Template '{template_name}' not found")
                return None
            
            template = self.templates[template_name]
            return template.create_video(content, visuals, channel_config, audio_path)
            
        except Exception as e:
            self.logger.log_error(f"Video creation failed: {e}")
            return None
