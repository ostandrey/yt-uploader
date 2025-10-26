#!/usr/bin/env python3
"""
Simple scheduler that uses the original working scripts.
No complex imports, just direct execution.
"""

import os
import sys
import time
import schedule
import subprocess
from datetime import datetime

def run_tech_video():
    """Run tech video creation using the original working script."""
    try:
        print(f"🎬 Creating tech video at {datetime.now().strftime('%H:%M:%S')}")
        
        # Use the original working script
        result = subprocess.run([
            sys.executable, 
            "scripts/main.py", 
            "--channel", "tech"
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ Tech video created successfully!")
            return True
        else:
            print(f"❌ Tech video creation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating tech video: {e}")
        return False

def is_active_hours():
    """Check if current time is within active hours (7 AM - 11 PM)."""
    current_hour = datetime.now().hour
    return 7 <= current_hour <= 23

def main():
    """Main scheduler function."""
    print("🚀 Simple YouTube Automation Scheduler")
    print("=" * 50)
    print("📅 Schedule:")
    print("   • Tech News: 8:00 AM, 2:00 PM, 8:00 PM")
    print("⏰ Active hours: 7:00 AM - 11:00 PM")
    print("💡 Press Ctrl+C to stop")
    print("=" * 50)
    
    # Set up schedule
    schedule.every().day.at("08:00").do(run_tech_video)
    schedule.every().day.at("14:00").do(run_tech_video)
    schedule.every().day.at("20:00").do(run_tech_video)
    
    print(f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⏳ Waiting for scheduled times...")
    
    try:
        while True:
            # Only run during active hours
            if is_active_hours():
                schedule.run_pending()
            
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\n👋 Scheduler stopped by user")
    except Exception as e:
        print(f"❌ Scheduler error: {e}")

if __name__ == "__main__":
    main()
