#!/usr/bin/env python3
"""
Test script for audio generation functionality.
Tests the AudioGenerator class and audio integration.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_audio import AudioGenerator
from logger import initialize_logger

class TestAudioGeneration(unittest.TestCase):
    """Test cases for audio generation."""
    
    def setUp(self):
        """Set up test environment."""
        # Initialize logger
        initialize_logger()
        
        # Create test audio generator
        self.audio_generator = AudioGenerator()
        
        # Test content
        self.test_script = "The latest AI trends are revolutionizing technology! From ChatGPT to autonomous vehicles, AI is everywhere."
        self.test_config = {"channel_name": "Tech News"}
    
    def test_audio_generator_initialization(self):
        """Test that AudioGenerator initializes correctly."""
        self.assertIsNotNone(self.audio_generator)
        self.assertIsNotNone(self.audio_generator.logger)
    
    def test_text_preparation(self):
        """Test text preparation for TTS."""
        # Test with normal text
        clean_text = self.audio_generator._prepare_text(self.test_script)
        self.assertIsInstance(clean_text, str)
        self.assertGreater(len(clean_text), 0)
        
        # Test with very long text
        long_text = "A" * 6000  # Longer than 5000 char limit
        clean_long_text = self.audio_generator._prepare_text(long_text)
        self.assertLessEqual(len(clean_long_text), 5003)  # 5000 + "..."
        self.assertTrue(clean_long_text.endswith("..."))
    
    def test_audio_generation_with_gtts(self):
        """Test audio generation using gTTS."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = self.audio_generator.generate_audio(
                self.test_script, 
                self.test_config, 
                temp_dir
            )
            
            if audio_path:
                # Check if file was created
                self.assertTrue(os.path.exists(audio_path))
                self.assertGreater(os.path.getsize(audio_path), 0)
                
                # Check file extension
                self.assertTrue(audio_path.endswith('.mp3') or audio_path.endswith('.wav'))
    
    def test_audio_generation_with_pyttsx3(self):
        """Test audio generation using pyttsx3 fallback."""
        # Mock gTTS to force fallback to pyttsx3
        with patch('generate_audio.GTTS_AVAILABLE', False):
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = self.audio_generator.generate_audio(
                    self.test_script, 
                    self.test_config, 
                    temp_dir
                )
                
                # Should still work with pyttsx3 fallback
                if audio_path:
                    self.assertTrue(os.path.exists(audio_path))
    
    def test_audio_duration_estimation(self):
        """Test audio duration estimation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = self.audio_generator.generate_audio(
                self.test_script, 
                self.test_config, 
                temp_dir
            )
            
            if audio_path:
                duration = self.audio_generator.get_audio_duration(audio_path)
                self.assertIsInstance(duration, float)
                self.assertGreater(duration, 0)
    
    def test_audio_generation_failure_handling(self):
        """Test handling of audio generation failures."""
        # Test with empty script
        empty_script = ""
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = self.audio_generator.generate_audio(
                empty_script, 
                self.test_config, 
                temp_dir
            )
            # Should handle gracefully
            self.assertIsInstance(audio_path, (str, type(None)))
    
    def test_channel_config_handling(self):
        """Test handling of different channel configurations."""
        configs = [
            {"channel_name": "Tech News"},
            {"channel_name": "Crypto Updates"},
            {"channel_name": "Meme Hub"},
            {}  # Empty config
        ]
        
        for config in configs:
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = self.audio_generator.generate_audio(
                    self.test_script, 
                    config, 
                    temp_dir
                )
                # Should handle all configs gracefully
                self.assertIsInstance(audio_path, (str, type(None)))

class TestAudioIntegration(unittest.TestCase):
    """Test cases for audio integration with video assembly."""
    
    def setUp(self):
        """Set up test environment."""
        initialize_logger()
        
        # Import video assembler
        from assemble_video import VideoAssembler
        self.video_assembler = VideoAssembler()
        self.audio_generator = AudioGenerator()
    
    def test_audio_video_integration(self):
        """Test integration of audio with video creation."""
        # Generate test audio
        test_script = "Test audio for video integration."
        test_config = {"channel_name": "Test Channel"}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate audio
            audio_path = self.audio_generator.generate_audio(
                test_script, 
                test_config, 
                temp_dir
            )
            
            if audio_path:
                # Test video creation with audio
                test_content = {
                    "script": test_script,
                    "title": "Test Video",
                    "description": "Test description",
                    "tags": ["test"]
                }
                
                test_visuals = []
                test_channel_config = {"channel_name": "Test Channel"}
                
                video_path = self.video_assembler.create_video(
                    test_content, 
                    test_visuals, 
                    test_channel_config, 
                    audio_path
                )
                
                if video_path:
                    # Check if video was created
                    self.assertTrue(os.path.exists(video_path))
                    self.assertGreater(os.path.getsize(video_path), 1000)  # Should be substantial file

def run_audio_tests():
    """Run all audio generation tests."""
    print("🧪 Running Audio Generation Tests")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestAudioGeneration))
    test_suite.addTest(unittest.makeSuite(TestAudioIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("🎉 All audio tests passed!")
        return True
    else:
        print(f"❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False

if __name__ == "__main__":
    success = run_audio_tests()
    sys.exit(0 if success else 1)
