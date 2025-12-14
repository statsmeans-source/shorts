#!/usr/bin/env python3
"""
YouTube OAuth Setup Script

One-time setup script for authenticating YouTube channels.
Runs the OAuth 2.0 flow and saves tokens for later use.

Usage:
    python setup_youtube_auth.py --channel motivation_tr
    
Requirements:
    1. Create a project in Google Cloud Console
    2. Enable YouTube Data API v3
    3. Create OAuth 2.0 credentials (Desktop application)
    4. Download client_secret.json and save as:
       ./credentials/{channel_name}_client_secret.json
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.youtube_uploader import YouTubeUploader, GOOGLE_API_AVAILABLE


DEFAULT_CREDENTIALS_DIR = project_root / "credentials"


def setup_channel(channel_name: str, credentials_dir: Path) -> bool:
    """
    Setup OAuth authentication for a YouTube channel.
    
    Args:
        channel_name: Unique identifier for the channel
        credentials_dir: Path to credentials directory
        
    Returns:
        True if setup successful
    """
    credentials_dir.mkdir(parents=True, exist_ok=True)
    
    client_secret_file = credentials_dir / f"{channel_name}_client_secret.json"
    
    # Check for client secret file
    if not client_secret_file.exists():
        logger.error(f"Client secret file not found: {client_secret_file}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("SETUP INSTRUCTIONS:")
        logger.info("=" * 60)
        logger.info("")
        logger.info("1. Go to Google Cloud Console:")
        logger.info("   https://console.cloud.google.com")
        logger.info("")
        logger.info("2. Create a new project or select existing one")
        logger.info("")
        logger.info("3. Enable YouTube Data API v3:")
        logger.info("   - Go to 'APIs & Services' > 'Library'")
        logger.info("   - Search 'YouTube Data API v3'")
        logger.info("   - Click 'Enable'")
        logger.info("")
        logger.info("4. Create OAuth 2.0 credentials:")
        logger.info("   - Go to 'APIs & Services' > 'Credentials'")
        logger.info("   - Click 'Create Credentials' > 'OAuth client ID'")
        logger.info("   - Application type: 'Desktop application'")
        logger.info("   - Download the JSON file")
        logger.info("")
        logger.info("5. Save the downloaded file as:")
        logger.info(f"   {client_secret_file}")
        logger.info("")
        logger.info("6. Run this script again")
        logger.info("=" * 60)
        return False
    
    logger.info(f"Setting up OAuth for channel: {channel_name}")
    logger.info(f"Using credentials: {client_secret_file}")
    logger.info("")
    logger.info("A browser window will open for authentication.")
    logger.info("Please sign in with the YouTube account for this channel.")
    logger.info("")
    
    # Create uploader and authenticate
    uploader = YouTubeUploader(
        credentials_dir=str(credentials_dir),
        channel_name=channel_name
    )
    
    if uploader.authenticate(interactive=True):
        logger.success("Authentication successful!")
        
        # Get and display channel info
        info = uploader.get_channel_info()
        if info:
            channel_title = info['snippet']['title']
            subscriber_count = info['statistics'].get('subscriberCount', 'N/A')
            video_count = info['statistics'].get('videoCount', 'N/A')
            
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"Channel: {channel_title}")
            logger.info(f"Subscribers: {subscriber_count}")
            logger.info(f"Videos: {video_count}")
            logger.info("=" * 60)
        
        token_file = credentials_dir / f"{channel_name}_token.json"
        logger.info(f"Token saved to: {token_file}")
        logger.info("")
        logger.info("You can now use this channel in automation.py")
        
        return True
    else:
        logger.error("Authentication failed!")
        return False


def list_configured_channels(credentials_dir: Path):
    """List all channels with saved tokens."""
    if not credentials_dir.exists():
        logger.info("No credentials directory found.")
        return
    
    token_files = list(credentials_dir.glob("*_token.json"))
    
    if not token_files:
        logger.info("No authenticated channels found.")
        return
    
    logger.info(f"Authenticated channels ({len(token_files)}):")
    for token_file in token_files:
        channel_name = token_file.stem.replace("_token", "")
        
        # Check if client secret also exists
        client_secret = credentials_dir / f"{channel_name}_client_secret.json"
        status = "✓" if client_secret.exists() else "⚠ (missing client_secret)"
        
        logger.info(f"  - {channel_name} {status}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube OAuth Setup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--channel',
        type=str,
        help='Channel name to authenticate'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List authenticated channels'
    )
    
    parser.add_argument(
        '--credentials-dir',
        type=str,
        default=str(DEFAULT_CREDENTIALS_DIR),
        help='Path to credentials directory'
    )
    
    args = parser.parse_args()
    
    # Use custom credentials dir if specified
    credentials_dir = Path(args.credentials_dir)
    
    # Check dependencies
    if not GOOGLE_API_AVAILABLE:
        logger.error("Google API libraries not installed!")
        logger.info("Run: pip install google-api-python-client google-auth-oauthlib")
        sys.exit(1)
    
    # List channels
    if args.list:
        list_configured_channels(credentials_dir)
        return
    
    # Setup channel
    if args.channel:
        success = setup_channel(args.channel, credentials_dir)
        sys.exit(0 if success else 1)
    
    # No arguments - show help
    parser.print_help()
    logger.info("")
    logger.info("Examples:")
    logger.info("  python setup_youtube_auth.py --channel motivation_tr")
    logger.info("  python setup_youtube_auth.py --list")


if __name__ == "__main__":
    main()
