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
    
    # 1. Setup config.toml
    config_file = root_dir / "config.toml"
    
    # Create default config structure
    config_data = {
        "app": {
            "llm_provider": "pollinations",
            "pexels_api_keys": [os.environ.get("PEXELS_API_KEY", "")],
            "video_source": "pexels",
            "log_level": "INFO"
        },
        "ui": {
            "font_name": "STHeitiMedium.ttc"
        }
    }
    
    with open(config_file, "w") as f:
        toml.dump(config_data, f)
    print(f"Created {config_file}")
    
    # 2. Setup YouTube Credentials
    # Users should put the content of their client_secret.json into CLIENT_SECRET_JSON secret
    client_secret_content = os.environ.get("CLIENT_SECRET_JSON")
    if client_secret_content:
        # Save for all configured channels (assuming logic handles names)
        # For simplicity, we save as a specific name that matches the channel
        # We need to know the channel name. Let's assume passed via env or hardcoded logic
        # For now, we'll save it as 'motivation_en_client_secret.json' based on our setup
        target_file = credentials_dir / "motivation_en_client_secret.json"
        with open(target_file, "w") as f:
            f.write(client_secret_content)
        print(f"Created {target_file}")
        
    # Users should put the content of their token.json into TOKEN_JSON secret
    token_content = os.environ.get("TOKEN_JSON")
    if token_content:
        target_file = credentials_dir / "motivation_en_token.json"
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
