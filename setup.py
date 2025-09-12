"""
Setup script for YouTube automation project.
Helps configure the project with API keys and initial setup.
"""

import os
import shutil
import json
from typing import Dict, List

def create_env_file():
    """Create .env file from template."""
    if os.path.exists('.env'):
        response = input(".env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Keeping existing .env file")
            return
    
    print("\n=== Creating .env file ===")
    print("Please provide your API keys:")
    
    # YouTube API keys
    print("\n--- YouTube API Configuration ---")
    tech_api_key = input("Tech channel API key: ").strip()
    tech_client_id = input("Tech channel Client ID: ").strip()
    tech_client_secret = input("Tech channel Client Secret: ").strip()
    
    crypto_api_key = input("Crypto channel API key: ").strip()
    crypto_client_id = input("Crypto channel Client ID: ").strip()
    crypto_client_secret = input("Crypto channel Client Secret: ").strip()
    
    memes_api_key = input("Memes channel API key: ").strip()
    memes_client_id = input("Memes channel Client ID: ").strip()
    memes_client_secret = input("Memes channel Client Secret: ").strip()
    
    # Other APIs
    print("\n--- Other API Configuration ---")
    abacus_api_key = input("Abacus.AI API key: ").strip()
    pexels_api_key = input("Pexels API key: ").strip()
    pixabay_api_key = input("Pixabay API key: ").strip()
    unsplash_access_key = input("Unsplash Access Key: ").strip()
    telegram_bot_token = input("Telegram Bot Token: ").strip()
    
    # Create .env content
    env_content = f"""# YouTube API Configuration for Tech Channel
YOUTUBE_TECH_API_KEY={tech_api_key}
YOUTUBE_TECH_CLIENT_ID={tech_client_id}
YOUTUBE_TECH_CLIENT_SECRET={tech_client_secret}
YOUTUBE_TECH_CREDENTIALS_FILE=credentials/tech_credentials.json

# YouTube API Configuration for Crypto Channel
YOUTUBE_CRYPTO_API_KEY={crypto_api_key}
YOUTUBE_CRYPTO_CLIENT_ID={crypto_client_id}
YOUTUBE_CRYPTO_CLIENT_SECRET={crypto_client_secret}
YOUTUBE_CRYPTO_CREDENTIALS_FILE=credentials/crypto_credentials.json

# YouTube API Configuration for Memes Channel
YOUTUBE_MEMES_API_KEY={memes_api_key}
YOUTUBE_MEMES_CLIENT_ID={memes_client_id}
YOUTUBE_MEMES_CLIENT_SECRET={memes_client_secret}
YOUTUBE_MEMES_CREDENTIALS_FILE=credentials/memes_credentials.json

# Abacus.AI Configuration
ABACUS_API_KEY={abacus_api_key}
ABACUS_API_URL=https://api.abacus.ai

# Stock Photo/Video APIs
PEXELS_API_KEY={pexels_api_key}
PIXABAY_API_KEY={pixabay_api_key}
UNSPLASH_ACCESS_KEY={unsplash_access_key}

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN={telegram_bot_token}
TELEGRAM_CHAT_ID=189878550

# Storage Configuration
STORAGE_TYPE=local
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your_minio_access_key_here
MINIO_SECRET_KEY=your_minio_secret_key_here

# OpenAI (backup for content generation)
OPENAI_API_KEY=your_openai_api_key_here

# Application Settings
LOG_LEVEL=INFO
MAX_RETRIES=3
VIDEO_QUALITY=high
DEFAULT_VIDEO_DURATION=60
"""
    
    # Write .env file
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ .env file created successfully!")

def setup_credentials():
    """Set up credentials files."""
    print("\n=== Setting up credentials ===")
    
    # Check if credentials directory exists
    if not os.path.exists('credentials'):
        os.makedirs('credentials')
        print("Created credentials directory")
    
    # Check for existing credentials files
    credential_files = [
        'tech_credentials.json',
        'crypto_credentials.json', 
        'memes_credentials.json'
    ]
    
    for cred_file in credential_files:
        file_path = os.path.join('credentials', cred_file)
        if not os.path.exists(file_path):
            print(f"\n⚠️  {cred_file} not found in credentials/ directory")
            print(f"Please copy your {cred_file} file to the credentials/ directory")
            print(f"Expected location: {os.path.abspath(file_path)}")
        else:
            print(f"✅ Found {cred_file}")

def create_gitignore():
    """Create .gitignore file."""
    gitignore_content = """# Environment variables
.env
*.env

# Credentials and tokens
credentials/
tokens/
*.json

# Logs
logs/
*.log

# Generated content
storage/
*.mp4
*.jpg
*.png
*.wav
*.mp3

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("✅ .gitignore file created")

def test_setup():
    """Test the setup by running basic imports."""
    print("\n=== Testing setup ===")
    
    try:
        # Test imports
        import requests
        import yaml
        import schedule
        print("✅ Basic dependencies imported successfully")
        
        # Test if .env exists
        if os.path.exists('.env'):
            print("✅ .env file found")
        else:
            print("❌ .env file not found")
        
        # Test if credentials directory exists
        if os.path.exists('credentials'):
            print("✅ credentials directory found")
        else:
            print("❌ credentials directory not found")
        
        # Test if tokens directory exists
        if os.path.exists('tokens'):
            print("✅ tokens directory found")
        else:
            print("❌ tokens directory not found")
        
        print("\n🎉 Setup test completed!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")

def main():
    """Main setup function."""
    print("🚀 YouTube Automation Project Setup")
    print("=" * 40)
    
    # Create .gitignore first
    create_gitignore()
    
    # Create .env file
    create_env_file()
    
    # Set up credentials
    setup_credentials()
    
    # Test setup
    test_setup()
    
    print("\n" + "=" * 40)
    print("🎯 Next Steps:")
    print("1. Copy your credentials JSON files to the credentials/ directory")
    print("2. Install dependencies: pip install -r requirements.txt")
    print("3. Test a single channel: python scripts/main.py --mode single --channel tech")
    print("4. Check logs in the logs/ directory")
    print("5. Monitor Telegram notifications")
    print("\n📚 For more information, see README.md")

if __name__ == "__main__":
    main()
