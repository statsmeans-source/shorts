"""
YouTube Video Upload Service

This module provides functionality to upload videos to YouTube using the YouTube Data API v3.
Supports OAuth 2.0 authentication and resumable uploads for reliability.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

from loguru import logger

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth-oauthlib")


# OAuth 2.0 scopes required for uploading videos
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly'  # For channel info
]

# Retry configuration
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


class YouTubeUploader:
    """
    YouTube video uploader with OAuth 2.0 authentication.
    
    Supports:
    - Token persistence and refresh
    - Resumable uploads
    - Retry on transient errors
    """
    
    def __init__(
        self,
        credentials_dir: str = "./credentials",
        channel_name: str = "default"
    ):
        """
        Initialize the YouTube uploader.
        
        Args:
            credentials_dir: Directory containing OAuth credentials
            channel_name: Unique identifier for the channel (used for token storage)
        """
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )
        
        self.credentials_dir = Path(credentials_dir)
        self.channel_name = channel_name
        self.credentials: Optional[Credentials] = None
        self.youtube = None
        
        # Token file path
        self.token_file = self.credentials_dir / f"{channel_name}_token.json"
        self.client_secret_file = self.credentials_dir / f"{channel_name}_client_secret.json"
        
    def authenticate(self, interactive: bool = True) -> bool:
        """
        Authenticate with YouTube API using OAuth 2.0.
        
        Args:
            interactive: If True, opens browser for authentication when needed
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Try to load existing token
            if self.token_file.exists():
                self.credentials = Credentials.from_authorized_user_file(
                    str(self.token_file), SCOPES
                )
            
            # Check if credentials need refresh or re-authentication
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    logger.info(f"Refreshing token for channel: {self.channel_name}")
                    self.credentials.refresh(Request())
                elif interactive:
                    logger.info(f"Starting OAuth flow for channel: {self.channel_name}")
                    if not self.client_secret_file.exists():
                        logger.error(f"Client secret file not found: {self.client_secret_file}")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.client_secret_file), SCOPES
                    )
                    self.credentials = flow.run_local_server(port=0)
                else:
                    logger.error("No valid credentials and interactive mode is disabled")
                    return False
                
                # Save the credentials for future use
                self._save_token()
            
            # Build the YouTube API client
            self.youtube = build('youtube', 'v3', credentials=self.credentials)
            logger.success(f"Successfully authenticated for channel: {self.channel_name}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def _save_token(self):
        """Save credentials to token file."""
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, 'w') as f:
            f.write(self.credentials.to_json())
        logger.info(f"Token saved to: {self.token_file}")
    
    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[list] = None,
        category_id: str = "22",  # People & Blogs
        privacy_status: str = "private",
        is_shorts: bool = True,
        notify_subscribers: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Path to the video file
            title: Video title (max 100 characters)
            description: Video description (max 5000 characters)
            tags: List of tags for the video
            category_id: YouTube category ID
            privacy_status: "private", "unlisted", or "public"
            is_shorts: If True, adds #Shorts to title for Shorts discovery
            notify_subscribers: Whether to notify subscribers
            
        Returns:
            Response dict with video ID and details, or None on failure
        """
        if not self.youtube:
            if not self.authenticate():
                return None
        
        # Validate video file
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
        
        # Prepare title for Shorts
        if is_shorts and "#Shorts" not in title:
            # Keep title under 100 chars
            shorts_suffix = " #Shorts"
            max_title_len = 100 - len(shorts_suffix)
            if len(title) > max_title_len:
                title = title[:max_title_len]
            title = f"{title}{shorts_suffix}"
        
        # Prepare request body
        body = {
            'snippet': {
                'title': title[:100],  # Max 100 chars
                'description': description[:5000],  # Max 5000 chars
                'tags': tags or [],
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False,
                'notifySubscribers': notify_subscribers
            }
        }
        
        # Create media upload object with resumable upload
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024 * 1024  # 1MB chunks
        )
        
        try:
            # Create insert request
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            # Execute with retry logic for resumable upload
            response = self._resumable_upload(request)
            
            if response:
                video_id = response.get('id')
                logger.success(f"Video uploaded successfully! ID: {video_id}")
                logger.info(f"URL: https://youtube.com/watch?v={video_id}")
                return response
            
            return None
            
        except HttpError as e:
            logger.error(f"HTTP error during upload: {e}")
            return None
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None
    
    def _resumable_upload(self, request) -> Optional[Dict[str, Any]]:
        """
        Execute resumable upload with retry logic.
        
        Args:
            request: YouTube API insert request
            
        Returns:
            Response dict on success, None on failure
        """
        response = None
        error = None
        retry = 0
        
        while response is None:
            try:
                logger.info("Uploading video...")
                status, response = request.next_chunk()
                
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")
                    
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    error = f"Retriable HTTP error {e.resp.status}: {e.content}"
                else:
                    raise
            except Exception as e:
                error = f"Error during upload: {e}"
            
            if error:
                logger.warning(error)
                retry += 1
                
                if retry > MAX_RETRIES:
                    logger.error("Max retries exceeded")
                    return None
                
                # Exponential backoff
                sleep_seconds = min(2 ** retry, 60)
                logger.info(f"Retrying in {sleep_seconds} seconds...")
                time.sleep(sleep_seconds)
                error = None
        
        return response
    
    def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the authenticated channel.
        
        Returns:
            Channel info dict or None on failure
        """
        if not self.youtube:
            if not self.authenticate():
                return None
        
        try:
            request = self.youtube.channels().list(
                part="snippet,statistics",
                mine=True
            )
            response = request.execute()
            
            if response.get('items'):
                return response['items'][0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return None


def upload_video_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    channel_name: str = "default",
    credentials_dir: str = "./credentials",
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to upload a video to YouTube.
    
    Args:
        video_path: Path to the video file
        title: Video title
        description: Video description
        channel_name: Channel identifier for credentials
        credentials_dir: Directory containing OAuth credentials
        **kwargs: Additional arguments passed to upload_video()
        
    Returns:
        Response dict with video ID and details, or None on failure
    """
    uploader = YouTubeUploader(
        credentials_dir=credentials_dir,
        channel_name=channel_name
    )
    
    return uploader.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        **kwargs
    )


if __name__ == "__main__":
    # Test the uploader
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python youtube_uploader.py <channel_name> <video_path>")
        sys.exit(1)
    
    channel = sys.argv[1]
    video = sys.argv[2]
    
    uploader = YouTubeUploader(channel_name=channel)
    
    if uploader.authenticate():
        info = uploader.get_channel_info()
        if info:
            print(f"Channel: {info['snippet']['title']}")
        
        result = uploader.upload_video(
            video_path=video,
            title="Test Video",
            description="Uploaded via MoneyPrinterTurbo automation",
            privacy_status="private"
        )
        
        if result:
            print(f"Upload successful! Video ID: {result['id']}")
