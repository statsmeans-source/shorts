import os
import json
import base64
from pathlib import Path
import toml

def setup_environment():
    """
    Setup the environment for GitHub Actions by creating necessary config and credential files
    from environment variables (secrets).
    """
    print("Setting up environment from secrets...")
    
    root_dir = Path(__file__).parent.parent
    credentials_dir = root_dir / "credentials"
    credentials_dir.mkdir(exist_ok=True)
    
    # Get channel name from environment (defaults to movies_en for backward compatibility)
    channel_name = os.environ.get("CHANNEL_NAME", "movies_en")
    print(f"Setting up for channel: {channel_name}")
    
    # 1. Setup config.toml
    config_file = root_dir / "config.toml"
    
    # Determine video source based on available API keys
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
    
    # Prefer Pixabay for copyright-free content
    video_source = "pixabay" if pixabay_key else "pexels"
    
    # Create default config structure
    config_data = {
        "app": {
            "llm_provider": "pollinations",
            "pexels_api_keys": [pexels_key] if pexels_key else [],
            "pixabay_api_keys": [pixabay_key] if pixabay_key else [],
            "video_source": video_source,
            "log_level": "INFO"
        },
        "ui": {
            "font_name": "STHeitiMedium.ttc"
        }
    }
    
    with open(config_file, "w") as f:
        toml.dump(config_data, f)
    print(f"Created {config_file} with video_source: {video_source}")
    
    # 2. Setup YouTube Credentials for the specific channel
    client_secret_content = os.environ.get("CLIENT_SECRET_JSON")
    if client_secret_content:
        target_file = credentials_dir / f"{channel_name}_client_secret.json"
        with open(target_file, "w") as f:
            f.write(client_secret_content)
        print(f"Created {target_file}")
        
    # Setup token for the specific channel
    token_content = os.environ.get("TOKEN_JSON")
    if token_content:
        target_file = credentials_dir / f"{channel_name}_token.json"
        with open(target_file, "w") as f:
            f.write(token_content)
        print(f"Created {target_file}")

    # 3. Setup channels.json if passed as secret (optional, otherwise uses repo file)
    channels_content = os.environ.get("CHANNELS_CONFIG")
    if channels_content:
        config_dir = root_dir / "config"
        config_dir.mkdir(exist_ok=True)
        with open(config_dir / "channels.json", "w") as f:
            f.write(channels_content)
        print("Created channels.json from secret")

if __name__ == "__main__":
    setup_environment()
