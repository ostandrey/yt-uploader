#!/usr/bin/env python3
"""
Simple launcher for YouTube automation.
Uses the original working scripts without complex imports.
"""

import os
import sys
from datetime import datetime

def main():
    """Main launcher function."""
    print("🚀 Simple YouTube Automation Launcher")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('scripts/main.py'):
        print("❌ Error: Please run this script from the project root directory")
        return
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ Error: .env file not found")
        return
    
    print("✅ Environment check passed")
    print(f"🕐 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📅 Schedule: Tech News at 8:00 AM, 2:00 PM, 8:00 PM")
    print()
    
    # Ask for confirmation
    response = input("🤔 Start simple automation? (y/n): ").lower().strip()
    
    if response not in ['y', 'yes']:
        print("👋 Automation cancelled")
        return
    
    print("🚀 Starting simple scheduler...")
    print("💡 Press Ctrl+C to stop")
    print("=" * 50)
    
    try:
        # Import and run the simple scheduler
        from simple_scheduler import main as scheduler_main
        scheduler_main()
        
    except KeyboardInterrupt:
        print("\n👋 Automation stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
