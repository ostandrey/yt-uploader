"""
YouTube upload script for YouTube automation project.
Handles OAuth authentication and video uploads for multiple channels.
"""

import os
import json
import pickle
from typing import Dict, Optional, List
from datetime import datetime
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from logger import get_logger

class YouTubeUploader:
    def __init__(self, channel_name: str, credentials_file: str, token_file: str):
        """
        Initialize YouTube uploader for a specific channel.
        
        Args:
            channel_name: Name of the YouTube channel
            credentials_file: Path to OAuth credentials JSON file
            token_file: Path to store/load OAuth token
        """
        self.channel_name = channel_name
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.logger = get_logger()
        
        # YouTube API scopes
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        
        # Initialize YouTube service
        self.youtube_service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with YouTube API using OAuth."""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
                self.logger.log_info(f"Loaded existing token for {self.channel_name}")
            except Exception as e:
                self.logger.log_warning(f"Failed to load token for {self.channel_name}: {e}")
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.log_info(f"Refreshed token for {self.channel_name}")
                except Exception as e:
                    self.logger.log_error(f"Failed to refresh token for {self.channel_name}: {e}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    self.logger.log_info(f"Completed OAuth flow for {self.channel_name}")
                except Exception as e:
                    self.logger.log_error(f"OAuth flow failed for {self.channel_name}: {e}")
                    raise
            
            # Save credentials for next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                self.logger.log_info(f"Saved token for {self.channel_name}")
            except Exception as e:
                self.logger.log_error(f"Failed to save token for {self.channel_name}: {e}")
        
        # Build YouTube service
        try:
            self.youtube_service = build('youtube', 'v3', credentials=creds)
            self.logger.log_success(f"YouTube service initialized for {self.channel_name}")
        except Exception as e:
            self.logger.log_error(f"Failed to initialize YouTube service for {self.channel_name}: {e}")
            raise
    
    def upload_video(self, video_path: str, title: str, description: str, 
                    tags: List[str], privacy_status: str = "unlisted") -> Optional[str]:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            privacy_status: 'private', 'unlisted', or 'public'
            
        Returns:
            YouTube video ID if successful, None otherwise
        """
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': '22'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': privacy_status
                }
            }
            
            # Create media upload object
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # Start upload
            self.logger.log_info(f"Starting upload for {self.channel_name}: {title}")
            
            insert_request = self.youtube_service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute upload
            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    self.logger.log_info(f"Upload progress for {self.channel_name}: {progress}%")
            
            if 'id' in response:
                video_id = response['id']
                self.logger.log_success(
                    f"Video uploaded successfully for {self.channel_name}: {video_id}"
                )
                self.logger.log_upload_attempt(
                    self.channel_name, 
                    video_path, 
                    video_id, 
                    "success"
                )
                return video_id
            else:
                raise Exception(f"Upload failed: {response}")
                
        except HttpError as e:
            error_details = {
                "error": str(e),
                "status_code": e.resp.status,
                "reason": e.resp.reason
            }
            self.logger.log_error(
                f"YouTube API error for {self.channel_name}: {e}",
                error_details=error_details
            )
            return None
            
        except Exception as e:
            self.logger.log_error(
                f"Upload failed for {self.channel_name}: {e}",
                error_details={"error": str(e), "video_path": video_path}
            )
            return None
    
    def update_video_privacy(self, video_id: str, privacy_status: str) -> bool:
        """
        Update video privacy status.
        
        Args:
            video_id: YouTube video ID
            privacy_status: 'private', 'unlisted', or 'public'
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current video details
            video_response = self.youtube_service.videos().list(
                part='status',
                id=video_id
            ).execute()
            
            if not video_response['items']:
                raise Exception(f"Video {video_id} not found")
            
            # Update privacy status
            video = video_response['items'][0]
            video['status']['privacyStatus'] = privacy_status
            
            update_response = self.youtube_service.videos().update(
                part='status',
                body=video
            ).execute()
            
            self.logger.log_info(
                f"Updated privacy status for {self.channel_name} video {video_id} to {privacy_status}"
            )
            return True
            
        except Exception as e:
            self.logger.log_error(
                f"Failed to update privacy for {self.channel_name} video {video_id}: {e}"
            )
            return False
    
    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video from YouTube.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.youtube_service.videos().delete(id=video_id).execute()
            self.logger.log_info(f"Deleted video {video_id} from {self.channel_name}")
            return True
            
        except Exception as e:
            self.logger.log_error(
                f"Failed to delete video {video_id} from {self.channel_name}: {e}"
            )
            return False
    
    def get_channel_info(self) -> Optional[Dict]:
        """
        Get channel information.
        
        Returns:
            Channel information dictionary or None
        """
        try:
            response = self.youtube_service.channels().list(
                part='snippet,statistics',
                mine=True
            ).execute()
            
            if response['items']:
                channel = response['items'][0]
                return {
                    'id': channel['id'],
                    'title': channel['snippet']['title'],
                    'subscriber_count': channel['statistics'].get('subscriberCount', '0'),
                    'video_count': channel['statistics'].get('videoCount', '0'),
                    'view_count': channel['statistics'].get('viewCount', '0')
                }
            else:
                return None
                
        except Exception as e:
            self.logger.log_error(f"Failed to get channel info for {self.channel_name}: {e}")
            return None

class YouTubeManager:
    """Manager class for handling multiple YouTube channels."""
    
    def __init__(self, config: Dict):
        """
        Initialize YouTube manager with channel configurations.
        
        Args:
            config: Configuration dictionary with channel settings
        """
        self.config = config
        self.uploaders = {}
        self.logger = get_logger()
        
        # Initialize uploaders for each channel
        self._initialize_uploaders()
    
    def _initialize_uploaders(self):
        """Initialize YouTube uploaders for all configured channels."""
        self.channels_config = {
            'tech': {
                'name': 'Tech Daily Updates',
                'credentials': self.config.get('YOUTUBE_TECH_CREDENTIALS_FILE'),
                'token': 'tokens/tech_token.json'
            },
            'crypto': {
                'name': 'Crypto Finance Digest',
                'credentials': self.config.get('YOUTUBE_CRYPTO_CREDENTIALS_FILE'),
                'token': 'tokens/crypto_token.json'
            },
            'memes': {
                'name': 'Daily Meme Hub',
                'credentials': self.config.get('YOUTUBE_MEMES_CREDENTIALS_FILE'),
                'token': 'tokens/memes_token.json'
            }
        }
        
        # Don't initialize uploaders at startup - initialize on demand
        self.logger.log_info("YouTube uploaders will be initialized on demand")
    
    def upload_to_channel(self, channel_key: str, video_path: str, 
                         title: str, description: str, tags: List[str],
                         privacy_status: str = "unlisted") -> Optional[str]:
        """
        Upload video to specific channel.
        
        Args:
            channel_key: Channel key ('tech', 'crypto', 'memes')
            video_path: Path to video file
            title: Video title
            description: Video description
            tags: List of tags
            privacy_status: Privacy status
            
        Returns:
            YouTube video ID if successful, None otherwise
        """
        # Initialize uploader for this channel if not already done
        if channel_key not in self.uploaders:
            if channel_key in self.channels_config:
                channel_info = self.channels_config[channel_key]
                if channel_info['credentials'] and os.path.exists(channel_info['credentials']):
                    try:
                        self.uploaders[channel_key] = YouTubeUploader(
                            channel_info['name'],
                            channel_info['credentials'],
                            channel_info['token']
                        )
                        self.logger.log_success(f"Initialized uploader for {channel_key}")
                    except Exception as e:
                        self.logger.log_error(f"Failed to initialize uploader for {channel_key}: {e}")
                        return None
                else:
                    self.logger.log_error(f"Credentials not found for {channel_key}")
                    return None
            else:
                self.logger.log_error(f"Channel configuration not found for: {channel_key}")
                return None
        
        return self.uploaders[channel_key].upload_video(
            video_path, title, description, tags, privacy_status
        )
    
    def get_channel_stats(self) -> Dict:
        """Get statistics for all channels."""
        stats = {}
        for channel_key, uploader in self.uploaders.items():
            try:
                channel_info = uploader.get_channel_info()
                if channel_info:
                    stats[channel_key] = channel_info
            except Exception as e:
                self.logger.log_error(f"Failed to get stats for {channel_key}: {e}")
        
        return stats

# Example usage
if __name__ == "__main__":
    # Test configuration
    config = {
        'YOUTUBE_TECH_CREDENTIALS_FILE': 'credentials/tech_credentials.json',
        'YOUTUBE_CRYPTO_CREDENTIALS_FILE': 'credentials/crypto_credentials.json',
        'YOUTUBE_MEMES_CREDENTIALS_FILE': 'credentials/memes_credentials.json'
    }
    
    # Initialize logger
    from logger import initialize_logger
    initialize_logger()
    
    # Test YouTube manager
    manager = YouTubeManager(config)
    
    # Get channel stats
    stats = manager.get_channel_stats()
    print("Channel Statistics:")
    for channel, info in stats.items():
        print(f"{channel}: {info['title']} - {info['subscriber_count']} subscribers")
