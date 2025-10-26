"""
Audio generation script for YouTube automation project.
Generates voiceover audio from text content using TTS services.
"""

import os
import tempfile
from typing import Dict, Optional
from datetime import datetime

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("Warning: gTTS not installed. Install with: pip install gtts")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("Warning: pyttsx3 not installed. Install with: pip install pyttsx3")

from logger import get_logger

class AudioGenerator:
    def __init__(self):
        """Initialize the audio generator."""
        self.logger = get_logger()
        
        # Initialize pyttsx3 engine if available
        self.tts_engine = None
        if PYTTSX3_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                self._configure_voice()
                self.logger.log_info("pyttsx3 TTS engine initialized")
            except Exception as e:
                self.logger.log_warning(f"Failed to initialize pyttsx3: {e}")
                self.tts_engine = None
    
    def _configure_voice(self):
        """Configure the TTS voice settings."""
        if not self.tts_engine:
            return
        
        try:
            # Get available voices
            voices = self.tts_engine.getProperty('voices')
            
            # Try to find a female voice (usually sounds better for content)
            for voice in voices:
                if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            # Set speech rate (words per minute)
            self.tts_engine.setProperty('rate', 180)  # Slightly faster than normal
            
            # Set volume (0.0 to 1.0)
            self.tts_engine.setProperty('volume', 0.9)
            
        except Exception as e:
            self.logger.log_warning(f"Failed to configure voice: {e}")
    
    def generate_audio(self, script: str, channel_config: Dict, output_dir: str = None) -> Optional[str]:
        """
        Generate audio file from script text.
        
        Args:
            script: Text content to convert to speech
            channel_config: Channel configuration
            output_dir: Directory to save audio file
            
        Returns:
            Path to generated audio file or None if failed
        """
        try:
            self.logger.log_info("Starting audio generation")
            
            # Clean and prepare text
            clean_text = self._prepare_text(script)
            
            # Create output directory
            if not output_dir:
                channel_name = channel_config.get("channel_name", "Tech News")
                output_dir = f"storage/{channel_name.lower().replace(' ', '_')}/audio"
            
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_filename = f"audio_{timestamp}.mp3"
            audio_path = os.path.join(output_dir, audio_filename)
            
            # Try different TTS methods
            success = False
            
            # Method 1: Try gTTS (Google Text-to-Speech) - better quality
            if GTTS_AVAILABLE and not success:
                success = self._generate_with_gtts(clean_text, audio_path)
            
            # Method 2: Try pyttsx3 (offline) - fallback
            if not success and self.tts_engine:
                success = self._generate_with_pyttsx3(clean_text, audio_path)
            
            if success:
                self.logger.log_success(f"Audio generated successfully: {audio_path}")
                return audio_path
            else:
                self.logger.log_error("All TTS methods failed")
                return None
                
        except Exception as e:
            self.logger.log_error(f"Audio generation failed: {e}")
            return None
    
    def _prepare_text(self, script: str) -> str:
        """Prepare text for TTS by cleaning and optimizing."""
        # Remove extra whitespace
        clean_text = ' '.join(script.split())
        
        # Limit length for TTS (most services have limits)
        if len(clean_text) > 5000:
            clean_text = clean_text[:5000] + "..."
        
        # Add pauses for better speech flow
        clean_text = clean_text.replace('.', '. ')
        clean_text = clean_text.replace('!', '! ')
        clean_text = clean_text.replace('?', '? ')
        
        return clean_text
    
    def _generate_with_gtts(self, text: str, output_path: str) -> bool:
        """Generate audio using Google Text-to-Speech."""
        try:
            self.logger.log_info("Using Google Text-to-Speech (gTTS)")
            
            # Create gTTS object
            tts = gTTS(text=text, lang='en', slow=False)
            
            # Save to file
            tts.save(output_path)
            
            # Verify file was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.log_warning(f"gTTS generation failed: {e}")
            return False
    
    def _generate_with_pyttsx3(self, text: str, output_path: str) -> bool:
        """Generate audio using pyttsx3 (offline TTS)."""
        try:
            self.logger.log_info("Using pyttsx3 (offline TTS)")
            
            # Save to temporary file first
            temp_path = output_path.replace('.mp3', '_temp.wav')
            
            # Generate audio
            self.tts_engine.save_to_file(text, temp_path)
            self.tts_engine.runAndWait()
            
            # Convert to MP3 if needed (basic conversion)
            if os.path.exists(temp_path):
                # For now, just rename the file
                # In production, you'd want to convert WAV to MP3
                os.rename(temp_path, output_path.replace('.mp3', '.wav'))
                output_path = output_path.replace('.mp3', '.wav')
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.log_warning(f"pyttsx3 generation failed: {e}")
            return False
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds."""
        try:
            if not os.path.exists(audio_path):
                return 0.0
            
            # Try to get duration using basic file size estimation
            # This is a rough estimate - for production, use librosa or similar
            file_size = os.path.getsize(audio_path)
            
            # Rough estimate: 1KB per second for compressed audio
            estimated_duration = file_size / 1000
            
            return max(estimated_duration, 10.0)  # Minimum 10 seconds
            
        except Exception as e:
            self.logger.log_warning(f"Failed to get audio duration: {e}")
            return 30.0  # Default 30 seconds

# Example usage
if __name__ == "__main__":
    # Test the audio generator
    from logger import initialize_logger
    initialize_logger()
    
    generator = AudioGenerator()
    
    # Test content
    test_script = "The latest AI trends are revolutionizing technology! From ChatGPT to autonomous vehicles, AI is everywhere. Machine learning algorithms are getting smarter, and we're seeing breakthroughs in natural language processing."
    test_config = {"channel_name": "Tech News"}
    
    audio_path = generator.generate_audio(test_script, test_config)
    if audio_path:
        print(f"Test audio created: {audio_path}")
        duration = generator.get_audio_duration(audio_path)
        print(f"Audio duration: {duration:.1f} seconds")
    else:
        print("Test audio creation failed")
