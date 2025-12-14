import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.channel_manager import ChannelManager
from app.services.youtube_uploader import YouTubeUploader

def check_auth():
    print("Checking authentication for motivation_en...")
    
    # Setup paths
    config_file = project_root / "config" / "channels.json"
    credentials_dir = project_root / "credentials"
    
    auth_file = credentials_dir / "motivation_en_token.json"
    print(f"Token file exists: {auth_file.exists()}")
    
    if not auth_file.exists():
        print("Token file missing!")
        return
        
    uploader = YouTubeUploader(
        credentials_dir=str(credentials_dir),
        channel_name="motivation_en"
    )
    
    if uploader.authenticate(interactive=False):
        print("SUCCESS: Authentication successful!")
        # Try to get channel info to be sure
        try:
            request = uploader.youtube.channels().list(
                part="snippet",
                mine=True
            )
            response = request.execute()
            print(f"Channel found: {response['items'][0]['snippet']['title']}")
        except Exception as e:
            print(f"Warning: Could not fetch channel info: {e}")
    else:
        print("FAILURE: Authentication failed.")

if __name__ == "__main__":
    check_auth()
