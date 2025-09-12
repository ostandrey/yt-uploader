"""
Smart scheduling system for YouTube automation.
Runs during active hours (7 AM - 11 PM) with intelligent content distribution.
"""

import os
import sys
import time
import schedule
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import signal

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger import initialize_logger, get_logger
from main import YouTubeAutomationPipeline

class SmartScheduler:
    """Smart scheduler that runs automation during active hours."""
    
    def __init__(self):
        self.logger = get_logger()
        self.pipeline = None
        self.is_running = False
        self.scheduled_jobs = []
        
        # Schedule configuration
        self.active_hours = {
            'start': 7,    # 7 AM
            'end': 23      # 11 PM
        }
        
        # Content schedule - spread videos throughout the day
        self.content_schedule = {
            'tech': {
                'times': ['08:00', '14:00', '20:00'],  # 8 AM, 2 PM, 8 PM
                'topics_per_day': 2,  # 2 tech videos per day
                'enabled': True
            },
            'crypto': {
                'times': ['09:00', '17:00'],  # 9 AM, 5 PM
                'topics_per_day': 1,  # 1 crypto video per day
                'enabled': False  # Enable when ready
            },
            'memes': {
                'times': ['12:00', '19:00'],  # 12 PM, 7 PM
                'topics_per_day': 1,  # 1 meme video per day
                'enabled': False  # Enable when ready
            }
        }
        
        # Statistics tracking
        self.stats = {
            'videos_created_today': 0,
            'last_video_time': None,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'start_time': datetime.now()
        }
    
    def initialize_pipeline(self):
        """Initialize the YouTube automation pipeline."""
        try:
            self.pipeline = YouTubeAutomationPipeline()
            self.logger.log_success("Pipeline initialized successfully")
            return True
        except Exception as e:
            self.logger.log_error(f"Failed to initialize pipeline: {e}")
            return False
    
    def setup_schedule(self):
        """Set up the daily schedule for all channels."""
        try:
            # Clear existing jobs
            schedule.clear()
            
            # Set up jobs for each enabled channel
            for channel, config in self.content_schedule.items():
                if config['enabled']:
                    self._setup_channel_schedule(channel, config)
            
            # Add daily statistics job
            schedule.every().day.at("23:30").do(self._daily_summary)
            
            # Add system health check
            schedule.every(30).minutes.do(self._health_check)
            
            self.logger.log_info("Schedule setup completed")
            self._log_schedule()
            
        except Exception as e:
            self.logger.log_error(f"Failed to setup schedule: {e}")
    
    def _setup_channel_schedule(self, channel: str, config: Dict):
        """Set up schedule for a specific channel."""
        try:
            for time_str in config['times']:
                # Create a job for this time
                job = schedule.every().day.at(time_str).do(
                    self._create_video_job, 
                    channel=channel,
                    time_slot=time_str
                )
                self.scheduled_jobs.append(job)
                
                self.logger.log_info(f"Scheduled {channel} video at {time_str}")
                
        except Exception as e:
            self.logger.log_warning(f"Failed to setup schedule for {channel}: {e}")
    
    def _create_video_job(self, channel: str, time_slot: str):
        """Create a video for a specific channel and time slot."""
        try:
            if not self._is_active_hours():
                self.logger.log_info(f"Skipping {channel} video - outside active hours")
                return
            
            self.logger.log_info(f"Starting {channel} video creation at {time_slot}")
            
            # Initialize pipeline if needed
            if not self.pipeline:
                if not self.initialize_pipeline():
                    return
            
            # Create video
            success = self.pipeline.create_video_for_channel(channel)
            
            if success:
                self.stats['videos_created_today'] += 1
                self.stats['successful_uploads'] += 1
                self.stats['last_video_time'] = datetime.now()
                self.logger.log_success(f"Successfully created {channel} video")
            else:
                self.stats['failed_uploads'] += 1
                self.logger.log_error(f"Failed to create {channel} video")
            
            # Add delay between videos to avoid rate limiting
            time.sleep(30)
            
        except Exception as e:
            self.logger.log_error(f"Error in video creation job: {e}")
            self.stats['failed_uploads'] += 1
    
    def _is_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        current_hour = datetime.now().hour
        return self.active_hours['start'] <= current_hour < self.active_hours['end']
    
    def _daily_summary(self):
        """Generate daily summary of automation activity."""
        try:
            self.logger.log_info("=== DAILY AUTOMATION SUMMARY ===")
            self.logger.log_info(f"Videos created today: {self.stats['videos_created_today']}")
            self.logger.log_info(f"Successful uploads: {self.stats['successful_uploads']}")
            self.logger.log_info(f"Failed uploads: {self.stats['failed_uploads']}")
            self.logger.log_info(f"Last video time: {self.stats['last_video_time']}")
            
            # Reset daily counters
            self.stats['videos_created_today'] = 0
            self.stats['last_video_time'] = None
            
            self.logger.log_info("=== END DAILY SUMMARY ===")
            
        except Exception as e:
            self.logger.log_error(f"Failed to generate daily summary: {e}")
    
    def _health_check(self):
        """Perform system health check."""
        try:
            if not self._is_active_hours():
                return
            
            # Check if pipeline is still working
            if self.pipeline:
                self.logger.log_info("System health check: OK")
            else:
                self.logger.log_warning("Pipeline not initialized - attempting to reinitialize")
                self.initialize_pipeline()
            
        except Exception as e:
            self.logger.log_error(f"Health check failed: {e}")
    
    def _log_schedule(self):
        """Log the current schedule."""
        self.logger.log_info("=== CURRENT SCHEDULE ===")
        for channel, config in self.content_schedule.items():
            if config['enabled']:
                self.logger.log_info(f"{channel.upper()}: {', '.join(config['times'])}")
        self.logger.log_info("=== END SCHEDULE ===")
    
    def start(self):
        """Start the scheduler."""
        try:
            self.logger.log_info("Starting YouTube Automation Scheduler")
            self.logger.log_info(f"Active hours: {self.active_hours['start']}:00 - {self.active_hours['end']}:00")
            
            # Initialize pipeline
            if not self.initialize_pipeline():
                self.logger.log_error("Failed to initialize pipeline - scheduler not started")
                return False
            
            # Setup schedule
            self.setup_schedule()
            
            # Set running flag
            self.is_running = True
            
            self.logger.log_success("Scheduler started successfully")
            self.logger.log_info("Press Ctrl+C to stop the scheduler")
            
            # Main scheduler loop
            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except KeyboardInterrupt:
                    self.logger.log_info("Received interrupt signal - stopping scheduler")
                    break
                except Exception as e:
                    self.logger.log_error(f"Error in scheduler loop: {e}")
                    time.sleep(60)  # Wait before retrying
            
            self.stop()
            return True
            
        except Exception as e:
            self.logger.log_error(f"Failed to start scheduler: {e}")
            return False
    
    def stop(self):
        """Stop the scheduler."""
        try:
            self.is_running = False
            schedule.clear()
            self.logger.log_info("Scheduler stopped")
        except Exception as e:
            self.logger.log_error(f"Error stopping scheduler: {e}")
    
    def get_status(self) -> Dict:
        """Get current scheduler status."""
        return {
            'is_running': self.is_running,
            'active_hours': self.active_hours,
            'stats': self.stats,
            'next_jobs': [str(job) for job in schedule.jobs[:5]]  # Next 5 jobs
        }

def main():
    """Main function to run the scheduler."""
    try:
        # Initialize logging
        initialize_logger()
        
        # Create and start scheduler
        scheduler = SmartScheduler()
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print("\nReceived interrupt signal - shutting down gracefully...")
            scheduler.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start the scheduler
        scheduler.start()
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
