"""
Main automation pipeline for YouTube automation project.
Orchestrates the entire pipeline from content generation to video upload.
"""

import os
import sys
import yaml
import json
import time
import random
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.content.script_generator import ContentGenerator
from src.content.dynamic_content import DynamicContentFetcher
from src.content.visual_fetcher import VisualContentFetcher
from src.upload.youtube_manager import YouTubeManager
from src.media.video_assembler import VideoAssembler
from src.media.audio_generator import AudioGenerator
from src.media.video_templates import VideoTemplateManager
from src.core.logger import initialize_logger, get_logger

class YouTubeAutomationPipeline:
    def __init__(self, config_file: str = ".env"):
        """
        Initialize the YouTube automation pipeline.
        
        Args:
            config_file: Path to the environment configuration file
        """
        self.config_file = config_file
        self.logger = None
        self.config = {}
        
        # Initialize components
        self.content_generator = None
        self.visual_fetcher = None
        self.youtube_manager = None
        self.video_assembler = None
        self.audio_generator = None
        self.template_manager = None
        self.dynamic_content = None
        
        # Initialize the pipeline
        self._initialize_pipeline()
    
    def _initialize_pipeline(self):
        """Initialize all pipeline components."""
        try:
            # Initialize logger first
            initialize_logger()
            self.logger = get_logger()
            self.logger.log_info("Initializing YouTube Automation Pipeline")
            
            # Load configuration
            self._load_config()
            
            # Initialize content generator
            self.content_generator = ContentGenerator(self.config)
            self.logger.log_info("Content generator initialized")
            
            # Initialize visual content fetcher
            self.visual_fetcher = VisualContentFetcher(
                pexels_api_key=self.config.get('PEXELS_API_KEY'),
                pixabay_api_key=self.config.get('PIXABAY_API_KEY'),
                unsplash_access_key=self.config.get('UNSPLASH_ACCESS_KEY'),
                abacus_api_key=self.config.get('ABACUS_API_KEY')
            )
            self.logger.log_info("Visual content fetcher initialized")
            
            # Initialize YouTube manager
            self.youtube_manager = YouTubeManager(self.config)
            self.logger.log_info("YouTube manager initialized")
            
            # Initialize video assembler
            self.video_assembler = VideoAssembler()
            self.logger.log_info("Video assembler initialized")
            
            # Initialize audio generator
            self.audio_generator = AudioGenerator()
            self.logger.log_info("Audio generator initialized")
            
            # Initialize video template manager
            self.template_manager = VideoTemplateManager()
            self.logger.log_info("Video template manager initialized")
            
            # Initialize dynamic content fetcher
            self.dynamic_content = DynamicContentFetcher()
            self.logger.log_info("Dynamic content fetcher initialized")
            
            self.logger.log_success("All pipeline components initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Pipeline initialization failed: {e}")
            else:
                print(f"Pipeline initialization failed: {e}")
            raise
    
    def _load_config(self):
        """Load configuration from environment file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self.config[key] = value
                self.logger.log_info("Configuration loaded successfully")
            else:
                self.logger.log_warning(f"Configuration file {self.config_file} not found")
        except Exception as e:
            self.logger.log_error(f"Failed to load configuration: {e}")
            raise
    
    def load_channel_config(self, channel_key: str) -> Dict:
        """Load configuration for a specific channel."""
        try:
            # Map channel keys to config files
            channel_mapping = {
                'tech': 'config/channels/tech.yaml',
                'crypto': 'config/channels/crypto.yaml',
                'memes': 'config/channels/memes.yaml'
            }
            
            config_path = channel_mapping.get(channel_key)
            if not config_path or not os.path.exists(config_path):
                raise FileNotFoundError(f"Channel config not found: {config_path}")
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            return config
            
        except Exception as e:
            self.logger.log_error(f"Failed to load channel config for {channel_key}: {e}")
            raise
    
    def create_video_for_channel(self, channel_key: str, topic: Optional[str] = None) -> bool:
        """
        Create a complete video for a specific channel.
        
        Args:
            channel_key: Channel key ('tech', 'crypto', 'memes')
            topic: Specific topic (if None, random topic will be selected)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load channel configuration
            channel_config = self.load_channel_config(channel_key)
            channel_name = channel_config["channel_name"]
            
            self.logger.log_info(f"Starting video creation for {channel_name}")
            
            # Step 1: Generate content
            if not topic:
                # Use dynamic content for tech channel, random topic for others
                if channel_key == 'tech':
                    self.logger.log_info("Fetching trending tech topics...")
                    trending_topics = self.dynamic_content.get_trending_tech_topics(count=3)
                    if trending_topics:
                        selected_topic = random.choice(trending_topics)
                        content = self.dynamic_content.generate_content_from_topic(selected_topic)
                        self.logger.log_info(f"Using trending topic: {content.get('title', 'Unknown')}")
                    else:
                        topic = self.content_generator.get_random_topic(channel_config)
                        content = self.content_generator.generate_script(channel_config, topic)
                else:
                    topic = self.content_generator.get_random_topic(channel_config)
                    content = self.content_generator.generate_script(channel_config, topic)
            else:
                self.logger.log_info(f"Generating content for topic: {topic}")
                content = self.content_generator.generate_script(channel_config, topic)
            
            # Validate content
            if not self.content_generator.validate_content(content, channel_config):
                self.logger.log_error(f"Content validation failed for {channel_name}")
                return False
            
            # Step 2: Get visuals
            self.logger.log_info(f"Fetching visuals for {channel_name}")
            visuals = self.visual_fetcher.get_visuals_for_script(
                content, 
                channel_config, 
                count=5
            )
            
            if not visuals:
                self.logger.log_warning(f"No visuals found for {channel_name}")
                # Continue without visuals or use fallback
            
            # Step 3: Generate audio
            audio_path = None
            if channel_config.get("settings", {}).get("voiceover", True):
                self.logger.log_info(f"Generating audio for {channel_name}")
                audio_path = self.audio_generator.generate_audio(
                    content["script"], 
                    channel_config
                )
            
            # Step 4: Generate thumbnail
            thumbnail_path = self.visual_fetcher.get_thumbnail_for_video(
                content["script"], 
                channel_config
            )
            
            # Step 5: Create video using template system
            template_name = channel_config.get("video_template", "tech_news")
            video_path = self.template_manager.create_video(
                template_name=template_name,
                content=content, 
                visuals=visuals, 
                channel_config=channel_config, 
                audio_path=audio_path
            )
            
            if not video_path:
                self.logger.log_error(f"Failed to create video for {channel_name}")
                return False
            
            # Step 5: Upload to YouTube
            privacy_status = "unlisted" if not channel_config.get("settings", {}).get("auto_upload", False) else "public"
            
            video_id = self.youtube_manager.upload_to_channel(
                channel_key=channel_key,
                video_path=video_path,
                title=content["title"],
                description=content["description"],
                tags=content["tags"],
                privacy_status=privacy_status
            )
            
            if video_id:
                self.logger.log_success(f"Video uploaded successfully: {video_id}")
                return True
            else:
                self.logger.log_error(f"Failed to upload video for {channel_name}")
                return False
                
        except Exception as e:
            self.logger.log_error(f"Video creation failed for {channel_key}: {e}")
            import traceback
            self.logger.log_error(f"Error details: {traceback.format_exc()}")
            return False
    
    def run_automation(self, channels: List[str] = None):
        """
        Run automation for specified channels.
        
        Args:
            channels: List of channel keys to automate (default: all enabled channels)
        """
        try:
            if not channels:
                channels = ['tech']  # Default to tech channel
            
            self.logger.log_info(f"Starting automation for channels: {channels}")
            
            for channel in channels:
                try:
                    self.logger.log_info(f"Processing channel: {channel}")
                    success = self.create_video_for_channel(channel)
                    
                    if success:
                        self.logger.log_success(f"Channel {channel} processed successfully")
                    else:
                        self.logger.log_error(f"Channel {channel} processing failed")
                    
                    # Add delay between channels
                    time.sleep(30)
                    
                except Exception as e:
                    self.logger.log_error(f"Error processing channel {channel}: {e}")
                    continue
            
            self.logger.log_info("Automation cycle completed")
            
        except Exception as e:
            self.logger.log_error(f"Automation failed: {e}")
            raise

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='YouTube Automation Pipeline')
    parser.add_argument('--channel', choices=['tech', 'crypto', 'memes'], 
                       help='Channel to create video for')
    parser.add_argument('--topic', type=str, help='Specific topic for the video')
    parser.add_argument('--all', action='store_true', help='Run automation for all channels')
    
    args = parser.parse_args()
    
    try:
        # Initialize pipeline
        pipeline = YouTubeAutomationPipeline()
        
        if args.all:
            # Run automation for all channels
            pipeline.run_automation()
        elif args.channel:
            # Create video for specific channel
            success = pipeline.create_video_for_channel(args.channel, args.topic)
            if success:
                print("✅ Video created successfully!")
            else:
                print("❌ Video creation failed!")
                sys.exit(1)
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
