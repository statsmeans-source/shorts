#!/usr/bin/env python3
"""
YouTube Shorts Automation System

Main entry point for the multi-channel YouTube Shorts automation.
Supports both scheduled mode (continuous) and one-shot mode.

Usage:
    # Start scheduler for all channels
    python automation.py --mode scheduler
    
    # Generate and upload one video for a specific channel
    python automation.py --once --channel motivation_tr
    
    # Dry run (generate video but don't upload)
    python automation.py --once --channel motivation_tr --dry-run
    
    # List configured channels
    python automation.py --list-channels
"""

import argparse
import sys
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.channel_manager import ChannelManager, create_sample_config
from app.services.scheduler import ShortsScheduler
from app.services.youtube_uploader import YouTubeUploader
from app.services import task as video_task
from app.models.schema import VideoParams


# Configuration paths
CONFIG_DIR = project_root / "config"
CREDENTIALS_DIR = project_root / "credentials"
CHANNELS_CONFIG = CONFIG_DIR / "channels.json"


def setup_logging():
    """Configure logging for the automation system."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/automation_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level="DEBUG"
    )


def generate_and_upload(
    channel_name: str,
    channel_manager: ChannelManager,
    topic: Optional[str] = None,
    dry_run: bool = False
) -> bool:
    """
    Generate a video and upload it to YouTube.
    
    Args:
        channel_name: Name of the channel
        channel_manager: ChannelManager instance
        topic: Optional specific topic (random if not provided)
        dry_run: If True, skip upload step
        
    Returns:
        True if successful
    """
    logger.info(f"Starting video generation for channel: {channel_name}")
    
    # Check rate limits
    if not dry_run and not channel_manager.can_upload(channel_name):
        logger.warning(f"Rate limit exceeded for {channel_name}, skipping...")
        return False
    
    # Get channel config
    channel = channel_manager.get_channel(channel_name)
    if not channel:
        logger.error(f"Channel not found: {channel_name}")
        return False
    
    # Get video parameters
    video_params = channel_manager.get_video_params(channel_name, topic)
    if not video_params:
        logger.error(f"Failed to get video parameters for {channel_name}")
        return False
    
    # Create unique task ID
    task_id = str(uuid.uuid4())
    
    logger.info(f"Generating video with topic: {video_params['video_subject']}")
    
    try:
        # Create VideoParams object
        params = VideoParams(
            video_subject=video_params['video_subject'],
            video_language=video_params['video_language'],
            voice_name=video_params['voice_name'],
            video_aspect=video_params['video_aspect'],
            video_clip_duration=video_params['video_clip_duration'],
            paragraph_number=video_params['paragraph_number'],
            subtitle_enabled=video_params['subtitle_enabled'],
            subtitle_position=video_params.get('subtitle_position', 'top'),
            video_count=1,
        )
        
        # Generate video
        result = video_task.start(task_id, params)
        
        if not result or not result.get('videos'):
            logger.error(f"Video generation failed for {channel_name}")
            return False
        
        video_path = result['videos'][0]
        video_script = result.get('script', '')
        
        logger.success(f"Video generated: {video_path}")
        
        if dry_run:
            logger.info("Dry run mode - skipping upload")
            return True
        
        # Prepare upload metadata
        title = video_params['video_subject'][:90]  # Leave room for #Shorts
        
        # Create description from script
        script_summary = video_script[:500] if video_script else ""
        description = channel.description_template.format(
            script_summary=script_summary
        )
        
        # Get uploader and authenticate
        uploader = channel_manager.get_uploader(channel_name)
        if not uploader:
            logger.error(f"Failed to get uploader for {channel_name}")
            return False
        
        if not uploader.authenticate(interactive=False):
            logger.error(f"Authentication failed for {channel_name}")
            return False
        
        # Upload video
        upload_result = uploader.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=channel.tags,
            privacy_status=channel.default_privacy,
            is_shorts=True,
            notify_subscribers=channel.notify_subscribers
        )
        
        if upload_result:
            video_id = upload_result.get('id')
            logger.success(f"Video uploaded! ID: {video_id}")
            logger.info(f"URL: https://youtube.com/watch?v={video_id}")
            
            # Record upload for rate limiting
            channel_manager.record_upload(channel_name)
            return True
        else:
            logger.error(f"Upload failed for {channel_name}")
            return False
            
    except Exception as e:
        logger.exception(f"Error during generation/upload: {e}")
        return False


def run_scheduler(channel_manager: ChannelManager, dry_run: bool = False):
    """
    Run the scheduler for all configured channels.
    
    Args:
        channel_manager: ChannelManager instance
        dry_run: If True, skip uploads
    """
    scheduler = ShortsScheduler(timezone="Europe/Istanbul", blocking=True)
    
    # Add jobs for each channel
    for channel_name in channel_manager.list_channels():
        channel = channel_manager.get_channel(channel_name)
        if not channel:
            continue
        
        logger.info(f"Adding schedule for {channel_name}: {channel.schedule}")
        
        scheduler.add_channel_job(
            channel_name=channel_name,
            schedule=channel.schedule,
            job_func=generate_and_upload,
            channel_manager=channel_manager,
            dry_run=dry_run
        )
    
    if not scheduler.list_jobs():
        logger.error("No jobs scheduled. Check channel configuration.")
        return
    
    logger.info("Starting scheduler...")
    scheduler.start()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Automation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--mode', 
        choices=['scheduler', 'once'],
        default='once',
        help='Run mode: scheduler (continuous) or once (single video)'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Generate and upload one video (shortcut for --mode once)'
    )
    
    parser.add_argument(
        '--channel',
        type=str,
        help='Channel name for one-shot mode'
    )
    
    parser.add_argument(
        '--topic',
        type=str,
        help='Specific topic for video generation'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate video but do not upload'
    )
    
    parser.add_argument(
        '--list-channels',
        action='store_true',
        help='List all configured channels'
    )
    
    parser.add_argument(
        '--create-sample-config',
        action='store_true',
        help='Create sample channel configuration'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=str(CHANNELS_CONFIG),
        help='Path to channels configuration file'
    )
    
    parser.add_argument(
        '--credentials-dir',
        type=str,
        default=str(CREDENTIALS_DIR),
        help='Path to credentials directory'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Create sample config if requested
    if args.create_sample_config:
        create_sample_config(args.config)
        logger.info("Sample configuration created. Please edit and add your channels.")
        return
    
    # Create directories
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    
    # Initialize channel manager
    channel_manager = ChannelManager(
        config_file=args.config,
        credentials_dir=args.credentials_dir
    )
    
    # List channels if requested
    if args.list_channels:
        channels = channel_manager.list_channels()
        if not channels:
            logger.info("No channels configured.")
            logger.info("Run with --create-sample-config to create a sample configuration.")
        else:
            logger.info(f"Configured channels ({len(channels)}):")
            for name in channels:
                ch = channel_manager.get_channel(name)
                if ch:
                    logger.info(f"  - {name}: {ch.schedule} ({len(ch.topics)} topics)")
        return
    
    # Check for channels
    if not channel_manager.list_channels():
        logger.warning("No channels configured!")
        logger.info("Creating sample configuration...")
        create_sample_config(args.config)
        channel_manager = ChannelManager(
            config_file=args.config,
            credentials_dir=args.credentials_dir
        )
    
    # Run in one-shot mode
    if args.once or args.mode == 'once':
        if not args.channel:
            # Use first channel if not specified
            channels = channel_manager.list_channels()
            if channels:
                args.channel = channels[0]
                logger.info(f"No channel specified, using: {args.channel}")
            else:
                logger.error("No channels available")
                return
        
        success = generate_and_upload(
            channel_name=args.channel,
            channel_manager=channel_manager,
            topic=args.topic,
            dry_run=args.dry_run
        )
        
        sys.exit(0 if success else 1)
    
    # Run scheduler
    if args.mode == 'scheduler':
        run_scheduler(channel_manager, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
