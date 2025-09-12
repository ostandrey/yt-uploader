#!/usr/bin/env python3
"""
Simple launcher for YouTube automation scheduler.
Run this script in the morning to start daily automation.
"""

import os
import sys
import time
from datetime import datetime

# Add scripts directory to path
sys.path.append('scripts')

def main():
    """Main launcher function."""
    print("🚀 YouTube Automation Launcher")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('scripts/main.py'):
        print("❌ Error: Please run this script from the project root directory")
        print("   Current directory should contain 'scripts' folder")
        return
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ Error: .env file not found")
        print("   Please make sure your .env file is in the project root")
        return
    
    print("✅ Environment check passed")
    
    # Show current time and schedule
    now = datetime.now()
    print(f"🕐 Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("📅 Automation will run from 7:00 AM to 11:00 PM")
    print("📺 Scheduled videos:")
    print("   • Tech News: 8:00 AM, 2:00 PM, 8:00 PM")
    print("   • Crypto: 9:00 AM, 5:00 PM (disabled)")
    print("   • Memes: 12:00 PM, 7:00 PM (disabled)")
    print()
    
    # Ask for confirmation
    response = input("🤔 Start automation now? (y/n): ").lower().strip()
    
    if response not in ['y', 'yes']:
        print("👋 Automation cancelled")
        return
    
    print("🚀 Starting automation scheduler...")
    print("💡 Press Ctrl+C to stop the scheduler")
    print("=" * 50)
    
    try:
        # Import and start the scheduler
        from scheduler import SmartScheduler
        
        scheduler = SmartScheduler()
        scheduler.start()
        
    except KeyboardInterrupt:
        print("\n👋 Automation stopped by user")
    except Exception as e:
        print(f"❌ Error starting automation: {e}")
        print("💡 Check the logs for more details")

if __name__ == "__main__":
    main()
