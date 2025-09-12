"""
Main automation script for YouTube automation project.
Orchestrates the entire pipeline from content generation to video upload.
"""

import os
import sys
import yaml
import json
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import initialize_logger, get_logger
from generate_script import ContentGenerator
from get_visuals import VisualContentFetcher
from upload_youtube import YouTubeManager
from assemble_video import VideoAssembler
from generate_audio import AudioGenerator

class YouTubeAutomationPipeline:
    def __init__(self, config_file: str = ".env"):
        """
        Initialize the YouTube automation pipeline.
        
        Args:
            config_file: Path to environment configuration file
        """
        self.config = self._load_config(config_file)
        self.logger = None
        self.content_generator = None
        self.visual_fetcher = None
        self.youtube_manager = None
        self.video_assembler = None
        self.audio_generator = None
        
        # Initialize components
        self._initialize_components()
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from environment file."""
        config = {}
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        
        return config
    
    def _initialize_components(self):
        """Initialize all pipeline components."""
        try:
            # Initialize logger
            self.logger = initialize_logger(
                telegram_token=self.config.get('TELEGRAM_BOT_TOKEN'),
                telegram_chat_id=self.config.get('TELEGRAM_CHAT_ID'),
                log_level=self.config.get('LOG_LEVEL', 'INFO')
            )
            
            # Initialize content generator
            self.content_generator = ContentGenerator(
                abacus_api_key=self.config.get('ABACUS_API_KEY'),
                openai_api_key=self.config.get('OPENAI_API_KEY')
            )
            
            # Initialize visual fetcher
            self.visual_fetcher = VisualContentFetcher(
                pexels_api_key=self.config.get('PEXELS_API_KEY'),
                pixabay_api_key=self.config.get('PIXABAY_API_KEY'),
                unsplash_access_key=self.config.get('UNSPLASH_ACCESS_KEY'),
                abacus_api_key=self.config.get('ABACUS_API_KEY')
            )
            
            # Initialize YouTube manager
            self.youtube_manager = YouTubeManager(self.config)
            
            # Initialize video assembler
            self.video_assembler = VideoAssembler()
            
            # Initialize audio generator
            self.audio_generator = AudioGenerator()
            
            self.logger.log_success("All pipeline components initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to initialize pipeline components: {e}")
            else:
                print(f"Failed to initialize pipeline components: {e}")
            raise
    
    def load_channel_config(self, channel_name: str) -> Dict:
        """Load configuration for a specific channel."""
        config_file = f"config/{channel_name.lower().replace(' ', '_')}.yaml"
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Channel config not found: {config_file}")
        
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
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
                topic = self.content_generator.get_random_topic(channel_config)
            
            self.logger.log_info(f"Generating content for topic: {topic}")
            content = self.content_generator.generate_script(channel_config, topic)
            
            # Validate content
            if not self.content_generator.validate_content(content, channel_config):
                self.logger.log_error(f"Content validation failed for {channel_name}")
                return False
            
            # Step 2: Get visuals
            self.logger.log_info(f"Fetching visuals for {channel_name}")
            visuals = self.visual_fetcher.get_visuals_for_script(
                content["script"], 
                channel_config, 
                count=5
            )
            
            if not visuals:
                self.logger.log_warning(f"No visuals found for {channel_name}")
                # Continue without visuals or use fallback
            
            # Step 3: Generate audio/voiceover
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
            
            # Step 5: Create video using video assembler
            video_path = self.video_assembler.create_video(content, visuals, channel_config, audio_path)
            
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
                self.logger.log_success(f"Video created and uploaded for {channel_name}: {video_id}")
                
                # Log video creation details
                self.logger.log_video_creation(
                    channel_name,
                    topic,
                    video_path,
                    duration=60.0,  # Placeholder
                    status="uploaded"
                )
                
                return True
            else:
                self.logger.log_error(f"Failed to upload video for {channel_name}")
                return False
                
        except Exception as e:
            self.logger.log_error(f"Video creation failed for {channel_key}: {e}")
            return False
    
    
    def run_daily_automation(self):
        """Run daily automation for all channels."""
        try:
            self.logger.log_info("Starting daily automation")
            
            channels = ['tech', 'crypto', 'memes']
            results = {}
            
            for channel in channels:
                try:
                    self.logger.log_info(f"Processing channel: {channel}")
                    success = self.create_video_for_channel(channel)
                    results[channel] = "success" if success else "failed"
                    
                    # Add delay between channels to avoid rate limits
                    time.sleep(30)
                    
                except Exception as e:
                    self.logger.log_error(f"Failed to process channel {channel}: {e}")
                    results[channel] = "error"
            
            # Log daily summary
            self.logger.log_daily_summary(results)
            
        except Exception as e:
            self.logger.log_error(f"Daily automation failed: {e}")
    
    def run_single_channel(self, channel_key: str, topic: Optional[str] = None):
        """Run automation for a single channel."""
        try:
            self.logger.log_info(f"Running single channel automation for: {channel_key}")
            success = self.create_video_for_channel(channel_key, topic)
            
            if success:
                self.logger.log_success(f"Single channel automation completed for {channel_key}")
            else:
                self.logger.log_error(f"Single channel automation failed for {channel_key}")
                
        except Exception as e:
            self.logger.log_error(f"Single channel automation error: {e}")
    
    def setup_scheduling(self):
        """Set up automated scheduling."""
        try:
            # Schedule daily automation at 9 AM and 3 PM
            schedule.every().day.at("09:00").do(self.run_daily_automation)
            schedule.every().day.at("15:00").do(self.run_daily_automation)
            
            self.logger.log_info("Scheduling set up: Daily automation at 9:00 AM and 3:00 PM")
            
        except Exception as e:
            self.logger.log_error(f"Failed to set up scheduling: {e}")
    
    def run_scheduler(self):
        """Run the scheduler loop."""
        self.logger.log_info("Starting scheduler loop")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.log_info("Scheduler stopped by user")
                break
            except Exception as e:
                self.logger.log_error(f"Scheduler error: {e}")
                time.sleep(60)

def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description="YouTube Automation Pipeline")
    parser.add_argument("--mode", choices=["single", "daily", "schedule"], 
                       default="single", help="Run mode")
    parser.add_argument("--channel", choices=["tech", "crypto", "memes"], 
                       help="Channel for single mode")
    parser.add_argument("--topic", help="Specific topic for single mode")
    parser.add_argument("--config", default=".env", help="Configuration file path")
    
    args = parser.parse_args()
    
    try:
        # Initialize pipeline
        pipeline = YouTubeAutomationPipeline(args.config)
        
        if args.mode == "single":
            if not args.channel:
                print("Error: --channel is required for single mode")
                return
            
            pipeline.run_single_channel(args.channel, args.topic)
            
        elif args.mode == "daily":
            pipeline.run_daily_automation()
            
        elif args.mode == "schedule":
            pipeline.setup_scheduling()
            pipeline.run_scheduler()
            
    except Exception as e:
        print(f"Pipeline error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
