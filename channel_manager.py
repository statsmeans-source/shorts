"""
Multi-Channel Manager Service

This module manages multiple YouTube channels, their configurations,
topic generation, and coordinated video creation workflows.
"""

import json
import random
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from app.services.youtube_uploader import YouTubeUploader
from app.services.script_cache import get_topic_cache


@dataclass
class ChannelConfig:
    """Configuration for a single YouTube channel."""
    name: str
    credentials_file: str
    topics: List[str]
    schedule: str  # Cron expression
    language: str = "en"
    voice: str = "en-US-JennyNeural-Female"
    
    # Video generation settings
    video_aspect: str = "9:16"  # Shorts format
    video_clip_duration: int = 5
    paragraph_number: int = 2
    subtitle_enabled: bool = True
    subtitle_position: str = "top"  # top, bottom, center
    
    # Upload settings
    default_privacy: str = "public"
    notify_subscribers: bool = True
    tags: List[str] = field(default_factory=list)
    description_template: str = ""
    
    # Rate limiting
    min_upload_interval_minutes: int = 30
    daily_video_limit: int = 3
    
    def __post_init__(self):
        if not self.description_template:
            self.description_template = (
                "{script_summary}\n\n"
                "---\n"
                "🎬 Bu video otomatik olarak oluşturulmuştur.\n"
                "#Shorts #Video"
            )


class ChannelManager:
    """
    Manages multiple YouTube channels and their video creation workflows.
    """
    
    def __init__(
        self, 
        config_file: str = "./config/channels.json",
        credentials_dir: str = "./credentials"
    ):
        """
        Initialize the channel manager.
        
        Args:
            config_file: Path to channels configuration file
            credentials_dir: Directory containing OAuth credentials
        """
        self.config_file = Path(config_file)
        self.credentials_dir = Path(credentials_dir)
        self.channels: Dict[str, ChannelConfig] = {}
        self.uploaders: Dict[str, YouTubeUploader] = {}
        self.upload_history: Dict[str, List[datetime]] = {}
        
        # Load channel configurations
        self._load_config()
    
    def _load_config(self):
        """Load channel configurations from file."""
        if not self.config_file.exists():
            logger.warning(f"Channel config not found: {self.config_file}")
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for channel_data in config_data.get('channels', []):
                channel = ChannelConfig(**channel_data)
                self.channels[channel.name] = channel
                self.upload_history[channel.name] = []
            
            logger.info(f"Loaded {len(self.channels)} channel configurations")
            
        except Exception as e:
            logger.error(f"Failed to load channel config: {e}")
    
    def save_config(self):
        """Save channel configurations to file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'channels': [
                {
                    'name': ch.name,
                    'credentials_file': ch.credentials_file,
                    'topics': ch.topics,
                    'schedule': ch.schedule,
                    'language': ch.language,
                    'voice': ch.voice,
                    'video_aspect': ch.video_aspect,
                    'video_clip_duration': ch.video_clip_duration,
                    'paragraph_number': ch.paragraph_number,
                    'subtitle_enabled': ch.subtitle_enabled,
                    'subtitle_position': ch.subtitle_position,
                    'default_privacy': ch.default_privacy,
                    'notify_subscribers': ch.notify_subscribers,
                    'tags': ch.tags,
                    'description_template': ch.description_template,
                    'min_upload_interval_minutes': ch.min_upload_interval_minutes,
                    'daily_video_limit': ch.daily_video_limit,
                }
                for ch in self.channels.values()
            ]
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved channel config to: {self.config_file}")
    
    def add_channel(self, channel: ChannelConfig) -> bool:
        """
        Add a new channel configuration.
        
        Args:
            channel: Channel configuration to add
            
        Returns:
            True if added successfully
        """
        if channel.name in self.channels:
            logger.warning(f"Channel already exists: {channel.name}")
            return False
        
        self.channels[channel.name] = channel
        self.upload_history[channel.name] = []
        self.save_config()
        logger.info(f"Added channel: {channel.name}")
        return True
    
    def remove_channel(self, channel_name: str) -> bool:
        """Remove a channel configuration."""
        if channel_name not in self.channels:
            logger.warning(f"Channel not found: {channel_name}")
            return False
        
        del self.channels[channel_name]
        self.upload_history.pop(channel_name, None)
        self.uploaders.pop(channel_name, None)
        self.save_config()
        logger.info(f"Removed channel: {channel_name}")
        return True
    
    def get_channel(self, channel_name: str) -> Optional[ChannelConfig]:
        """Get a channel configuration by name."""
        return self.channels.get(channel_name)
    
    def list_channels(self) -> List[str]:
        """Get list of all channel names."""
        return list(self.channels.keys())
    
    def get_uploader(self, channel_name: str) -> Optional[YouTubeUploader]:
        """
        Get or create a YouTubeUploader for a channel.
        
        Args:
            channel_name: Name of the channel
            
        Returns:
            YouTubeUploader instance or None if channel not found
        """
        if channel_name not in self.channels:
            logger.error(f"Channel not found: {channel_name}")
            return None
        
        if channel_name not in self.uploaders:
            channel = self.channels[channel_name]
            self.uploaders[channel_name] = YouTubeUploader(
                credentials_dir=str(self.credentials_dir),
                channel_name=channel_name
            )
        
        return self.uploaders[channel_name]
    
    def get_random_topic(self, channel_name: str) -> Optional[str]:
        """
        Get a smart topic for video generation.
        Uses topic history cache to avoid repetition - prefers unused topics,
        falls back to least-used ones.
        
        Args:
            channel_name: Name of the channel
            
        Returns:
            Selected topic string or None
        """
        channel = self.channels.get(channel_name)
        if not channel or not channel.topics:
            return None
        
        # Use smart topic selection from cache
        cache = get_topic_cache()
        selected_topic = cache.get_smart_topic(channel_name, channel.topics)
        
        # Record the usage
        cache.record_usage(channel_name, selected_topic)
        
        return selected_topic
    
    def can_upload(self, channel_name: str) -> bool:
        """
        Check if channel can upload based on rate limits.
        
        Args:
            channel_name: Name of the channel
            
        Returns:
            True if upload is allowed
        """
        channel = self.channels.get(channel_name)
        if not channel:
            return False
        
        history = self.upload_history.get(channel_name, [])
        now = datetime.now()
        
        # Clean old history (keep only today's uploads)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        history = [t for t in history if t >= today_start]
        self.upload_history[channel_name] = history
        
        # Check daily limit
        if len(history) >= channel.daily_video_limit:
            logger.warning(f"Daily limit reached for {channel_name}: {len(history)}/{channel.daily_video_limit}")
            return False
        
        # Check interval
        if history:
            last_upload = max(history)
            minutes_since = (now - last_upload).total_seconds() / 60
            if minutes_since < channel.min_upload_interval_minutes:
                logger.warning(
                    f"Upload interval not met for {channel_name}: "
                    f"{minutes_since:.1f}/{channel.min_upload_interval_minutes} min"
                )
                return False
        
        return True
    
    def record_upload(self, channel_name: str):
        """Record an upload timestamp for rate limiting."""
        if channel_name not in self.upload_history:
            self.upload_history[channel_name] = []
        self.upload_history[channel_name].append(datetime.now())
    
    def get_video_params(self, channel_name: str, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get video generation parameters for a channel.
        
        Args:
            channel_name: Name of the channel
            topic: Optional specific topic to use
            
        Returns:
            Dict of parameters for VideoParams or None
        """
        channel = self.channels.get(channel_name)
        if not channel:
            return None
        
        if topic is None:
            topic = self.get_random_topic(channel_name)
        
        if not topic:
            logger.error(f"No topics configured for channel: {channel_name}")
            return None
        
        return {
            'video_subject': topic,
            'video_language': channel.language,
            'voice_name': channel.voice,
            'video_aspect': channel.video_aspect,
            'video_clip_duration': channel.video_clip_duration,
            'paragraph_number': channel.paragraph_number,
            'subtitle_enabled': channel.subtitle_enabled,
            'subtitle_position': channel.subtitle_position,
        }
    
    def authenticate_channel(self, channel_name: str, interactive: bool = True) -> bool:
        """
        Authenticate a channel with YouTube API.
        
        Args:
            channel_name: Name of the channel
            interactive: If True, opens browser for authentication
            
        Returns:
            True if authentication successful
        """
        uploader = self.get_uploader(channel_name)
        if not uploader:
            return False
        
        return uploader.authenticate(interactive=interactive)
    
    def authenticate_all(self, interactive: bool = False) -> Dict[str, bool]:
        """
        Authenticate all configured channels.
        
        Args:
            interactive: If True, opens browser for authentication
            
        Returns:
            Dict of channel_name -> success status
        """
        results = {}
        for channel_name in self.channels:
            results[channel_name] = self.authenticate_channel(
                channel_name, interactive=interactive
            )
        return results


def create_sample_config(config_file: str = "./config/channels.json"):
    """Create a sample channel configuration file."""
    sample_config = {
        "channels": [
            {
                "name": "motivation_tr",
                "credentials_file": "motivation_tr_client_secret.json",
                "topics": [
                    "başarı hikayeleri",
                    "motivasyon sözleri",
                    "kişisel gelişim",
                    "hayat dersleri",
                    "pozitif düşünce"
                ],
                "schedule": "0 9,15,21 * * *",
                "language": "tr",
                "voice": "tr-TR-EmelNeural-Female",
                "tags": ["motivasyon", "başarı", "kişisel gelişim", "türkçe"],
                "daily_video_limit": 3
            },
            {
                "name": "tech_en",
                "credentials_file": "tech_en_client_secret.json",
                "topics": [
                    "artificial intelligence future",
                    "technology trends 2024",
                    "programming tips",
                    "tech innovations",
                    "digital transformation"
                ],
                "schedule": "0 10,18 * * *",
                "language": "en",
                "voice": "en-US-JennyNeural-Female",
                "tags": ["tech", "technology", "AI", "programming"],
                "daily_video_limit": 2
            }
        ]
    }
    
    config_path = Path(config_file)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(sample_config, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Sample config created at: {config_path}")
    return config_path


if __name__ == "__main__":
    # Create sample configuration
    create_sample_config()
    
    # Test loading
    manager = ChannelManager()
    
    print(f"Loaded channels: {manager.list_channels()}")
    
    for name in manager.list_channels():
        channel = manager.get_channel(name)
        print(f"\nChannel: {name}")
        print(f"  Topics: {channel.topics}")
        print(f"  Schedule: {channel.schedule}")
        print(f"  Language: {channel.language}")
