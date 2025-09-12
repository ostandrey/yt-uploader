"""
Logging and notification system for YouTube automation project.
Handles logging to files and sending notifications via Telegram.
"""

import logging
import os
import requests
from datetime import datetime
from typing import Optional, Dict, Any
import json

class YouTubeAutomationLogger:
    def __init__(self, log_level: str = "INFO", telegram_token: Optional[str] = None, 
                 telegram_chat_id: Optional[str] = None):
        """
        Initialize the logger with file logging and Telegram notifications.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            telegram_token: Telegram bot token for notifications
            telegram_chat_id: Telegram chat ID for notifications
        """
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Set up file logging
        self.setup_file_logging(log_level)
        
        # Set up console logging
        self.setup_console_logging(log_level)
        
        self.logger = logging.getLogger("youtube_automation")
        
    def setup_file_logging(self, log_level: str):
        """Set up file logging with rotation."""
        log_file = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logging.getLogger("youtube_automation").addHandler(file_handler)
        
    def setup_console_logging(self, log_level: str):
        """Set up console logging."""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logging.getLogger("youtube_automation").addHandler(console_handler)
        
    def log_info(self, message: str, channel: Optional[str] = None):
        """Log info message."""
        if channel:
            message = f"[{channel}] {message}"
        self.logger.info(message)
        
    def log_warning(self, message: str, channel: Optional[str] = None):
        """Log warning message."""
        if channel:
            message = f"[{channel}] {message}"
        self.logger.warning(message)
        
    def log_error(self, message: str, channel: Optional[str] = None, 
                  error_details: Optional[Dict[str, Any]] = None):
        """Log error message with optional details."""
        if channel:
            message = f"[{channel}] {message}"
        
        if error_details:
            message += f" | Details: {json.dumps(error_details, default=str)}"
            
        self.logger.error(message)
        
        # Send Telegram notification for errors
        if self.telegram_token and self.telegram_chat_id:
            self.send_telegram_notification(f"❌ ERROR: {message}")
        
    def log_success(self, message: str, channel: Optional[str] = None):
        """Log success message."""
        if channel:
            message = f"[{channel}] {message}"
        self.logger.info(f"✅ {message}")
        
        # Send Telegram notification for successes
        if self.telegram_token and self.telegram_chat_id:
            self.send_telegram_notification(f"✅ SUCCESS: {message}")
            
    def send_telegram_notification(self, message: str):
        """Send notification to Telegram."""
        if not self.telegram_token or not self.telegram_chat_id:
            return
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            # Log the error but don't send another notification to avoid loops
            self.logger.error(f"Failed to send Telegram notification: {e}")
            
    def log_video_creation(self, channel: str, topic: str, video_path: str, 
                          duration: float, status: str):
        """Log video creation details."""
        message = f"Video created - Topic: {topic}, Duration: {duration:.1f}s, Status: {status}"
        self.log_info(message, channel)
        
        # Log to separate video log file
        video_log_file = f"logs/videos_{datetime.now().strftime('%Y%m%d')}.log"
        with open(video_log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"{timestamp} | {channel} | {topic} | {video_path} | {duration:.1f}s | {status}\n")
            
    def log_upload_attempt(self, channel: str, video_path: str, youtube_id: Optional[str] = None, 
                          status: str = "attempted"):
        """Log YouTube upload attempts."""
        message = f"Upload {status} - Video: {os.path.basename(video_path)}"
        if youtube_id:
            message += f", YouTube ID: {youtube_id}"
            
        self.log_info(message, channel)
        
    def log_daily_summary(self, summary: Dict[str, Any]):
        """Log daily summary of activities."""
        summary_message = "📊 Daily Summary:\n"
        for key, value in summary.items():
            summary_message += f"• {key}: {value}\n"
            
        self.log_info(summary_message)
        
        # Send daily summary to Telegram
        if self.telegram_token and self.telegram_chat_id:
            self.send_telegram_notification(summary_message)
            
    def log_api_usage(self, service: str, endpoint: str, status: str, 
                     response_time: Optional[float] = None):
        """Log API usage for monitoring."""
        message = f"API {service} - {endpoint} - {status}"
        if response_time:
            message += f" - {response_time:.2f}s"
            
        self.log_info(message)
        
    def log_content_generation(self, channel: str, content_type: str, 
                              topic: str, success: bool, details: Optional[Dict] = None):
        """Log content generation attempts."""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        message = f"Content generation {status} - Type: {content_type}, Topic: {topic}"
        
        if details:
            message += f" | Details: {json.dumps(details, default=str)}"
            
        if success:
            self.log_success(message, channel)
        else:
            self.log_error(message, channel, details)

# Global logger instance
logger = None

def initialize_logger(telegram_token: Optional[str] = None, 
                     telegram_chat_id: Optional[str] = None,
                     log_level: str = "INFO"):
    """Initialize the global logger instance."""
    global logger
    logger = YouTubeAutomationLogger(
        log_level=log_level,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id
    )
    return logger

def get_logger() -> YouTubeAutomationLogger:
    """Get the global logger instance."""
    if logger is None:
        raise RuntimeError("Logger not initialized. Call initialize_logger() first.")
    return logger




