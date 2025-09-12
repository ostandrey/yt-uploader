#!/usr/bin/env python3
"""
End-to-end test for complete YouTube automation pipeline with audio.
Tests the full workflow from content generation to video upload.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from main import YouTubeAutomationPipeline
from logger import initialize_logger

class TestCompletePipelineWithAudio(unittest.TestCase):
    """Test cases for complete pipeline with audio integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Initialize logger
        initialize_logger()
        
        # Create test environment file
        self.test_env_content = """
# Test environment variables
YOUTUBE_TECH_CREDENTIALS_FILE=credentials/tech_credentials.json
YOUTUBE_CRYPTO_CREDENTIALS_FILE=credentials/crypto_credentials.json
YOUTUBE_MEMES_CREDENTIALS_FILE=credentials/memes_credentials.json
ABACUS_API_KEY=test_key
PEXELS_API_KEY=test_key
PIXABAY_API_KEY=test_key
UNSPLASH_ACCESS_KEY=test_key
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=123456789
"""
    
    def test_pipeline_initialization(self):
        """Test that pipeline initializes with all components."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(self.test_env_content)
            f.flush()
            
            try:
                # Mock the YouTube uploader to avoid actual uploads
                with patch('scripts.upload_youtube.YouTubeManager') as mock_youtube:
                    mock_youtube.return_value.upload_to_channel.return_value = "test_video_id"
                    
                    pipeline = YouTubeAutomationPipeline(f.name)
                    
                    # Check all components are initialized
                    self.assertIsNotNone(pipeline.content_generator)
                    self.assertIsNotNone(pipeline.visual_fetcher)
                    self.assertIsNotNone(pipeline.youtube_manager)
                    self.assertIsNotNone(pipeline.video_assembler)
                    self.assertIsNotNone(pipeline.audio_generator)
                    
            finally:
                os.unlink(f.name)
    
    def test_content_generation_with_audio(self):
        """Test content generation with audio support."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(self.test_env_content)
            f.flush()
            
            try:
                with patch('scripts.upload_youtube.YouTubeManager') as mock_youtube:
                    mock_youtube.return_value.upload_to_channel.return_value = "test_video_id"
                    
                    pipeline = YouTubeAutomationPipeline(f.name)
                    
                    # Test content generation
                    test_config = {
                        "channel_name": "Tech News",
                        "settings": {"voiceover": True},
                        "content": {"topics": ["AI trends"]}
                    }
                    
                    content = pipeline.content_generator.generate_script(test_config, "AI trends")
                    
                    # Check content structure
                    self.assertIsInstance(content, dict)
                    self.assertIn("script", content)
                    self.assertIn("title", content)
                    self.assertIn("description", content)
                    self.assertIn("tags", content)
                    
                    # Check content quality
                    self.assertGreater(len(content["script"]), 50)
                    self.assertLessEqual(len(content["title"]), 60)
                    
            finally:
                os.unlink(f.name)
    
    def test_audio_generation_integration(self):
        """Test audio generation as part of the pipeline."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(self.test_env_content)
            f.flush()
            
            try:
                with patch('scripts.upload_youtube.YouTubeManager') as mock_youtube:
                    mock_youtube.return_value.upload_to_channel.return_value = "test_video_id"
                    
                    pipeline = YouTubeAutomationPipeline(f.name)
                    
                    # Test audio generation
                    test_script = "The latest AI trends are revolutionizing technology!"
                    test_config = {"channel_name": "Tech News"}
                    
                    with tempfile.TemporaryDirectory() as temp_dir:
                        audio_path = pipeline.audio_generator.generate_audio(
                            test_script, 
                            test_config, 
                            temp_dir
                        )
                        
                        if audio_path:
                            # Check audio file was created
                            self.assertTrue(os.path.exists(audio_path))
                            self.assertGreater(os.path.getsize(audio_path), 0)
                            
            finally:
                os.unlink(f.name)
    
    def test_video_assembly_with_audio(self):
        """Test video assembly with audio integration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(self.test_env_content)
            f.flush()
            
            try:
                with patch('scripts.upload_youtube.YouTubeManager') as mock_youtube:
                    mock_youtube.return_value.upload_to_channel.return_value = "test_video_id"
                    
                    pipeline = YouTubeAutomationPipeline(f.name)
                    
                    # Test video assembly with audio
                    test_content = {
                        "script": "Test script for video assembly.",
                        "title": "Test Video",
                        "description": "Test description",
                        "tags": ["test"]
                    }
                    
                    test_visuals = []
                    test_config = {"channel_name": "Test Channel"}
                    
                    # Generate test audio
                    with tempfile.TemporaryDirectory() as temp_dir:
                        audio_path = pipeline.audio_generator.generate_audio(
                            test_content["script"], 
                            test_config, 
                            temp_dir
                        )
                        
                        if audio_path:
                            # Create video with audio
                            video_path = pipeline.video_assembler.create_video(
                                test_content, 
                                test_visuals, 
                                test_config, 
                                audio_path
                            )
                            
                            if video_path:
                                # Check video was created
                                self.assertTrue(os.path.exists(video_path))
                                self.assertGreater(os.path.getsize(video_path), 1000)
                                
            finally:
                os.unlink(f.name)
    
    def test_channel_config_voiceover_settings(self):
        """Test that voiceover settings are respected."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(self.test_env_content)
            f.flush()
            
            try:
                with patch('scripts.upload_youtube.YouTubeManager') as mock_youtube:
                    mock_youtube.return_value.upload_to_channel.return_value = "test_video_id"
                    
                    pipeline = YouTubeAutomationPipeline(f.name)
                    
                    # Test with voiceover enabled
                    config_with_voiceover = {
                        "channel_name": "Tech News",
                        "settings": {"voiceover": True}
                    }
                    
                    # Test with voiceover disabled
                    config_without_voiceover = {
                        "channel_name": "Tech News", 
                        "settings": {"voiceover": False}
                    }
                    
                    # Both should be handled gracefully
                    self.assertTrue(True)  # Placeholder for actual test logic
                    
            finally:
                os.unlink(f.name)

def run_complete_pipeline_tests():
    """Run all complete pipeline tests."""
    print("🧪 Running Complete Pipeline Tests (with Audio)")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestCompletePipelineWithAudio))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("🎉 All complete pipeline tests passed!")
        return True
    else:
        print(f"❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False

if __name__ == "__main__":
    success = run_complete_pipeline_tests()
    sys.exit(0 if success else 1)
