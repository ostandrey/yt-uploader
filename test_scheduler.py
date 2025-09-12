#!/usr/bin/env python3
"""
Test scheduler for YouTube automation.
Creates a video immediately to test the system.
"""

import os
import sys
import time
from datetime import datetime

# Add scripts directory to path
sys.path.append('scripts')

def test_automation():
    """Test the automation system by creating a video immediately."""
    print("🧪 Testing YouTube Automation System")
    print("=" * 50)
    
    try:
        # Import the main pipeline
        from main import YouTubeAutomationPipeline
        
        print("✅ Importing pipeline...")
        pipeline = YouTubeAutomationPipeline()
        
        print("✅ Pipeline initialized successfully")
        print("🎬 Creating test video...")
        
        # Create a test video
        success = pipeline.create_video_for_channel('tech')
        
        if success:
            print("🎉 SUCCESS: Test video created and uploaded!")
            print("📺 Check your YouTube channel for the new video")
        else:
            print("❌ FAILED: Test video creation failed")
            print("📋 Check the logs for error details")
        
        return success
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scheduler():
    """Test the scheduler system."""
    print("\n🕐 Testing Scheduler System")
    print("=" * 50)
    
    try:
        from scheduler import SmartScheduler
        
        print("✅ Creating scheduler...")
        scheduler = SmartScheduler()
        
        print("✅ Scheduler created successfully")
        print("📅 Current schedule:")
        
        # Show the schedule
        for channel, config in scheduler.content_schedule.items():
            if config['enabled']:
                print(f"   • {channel.upper()}: {', '.join(config['times'])}")
        
        print(f"⏰ Active hours: {scheduler.active_hours['start']}:00 - {scheduler.active_hours['end']}:00")
        
        # Check if we're in active hours
        current_hour = datetime.now().hour
        if scheduler._is_active_hours():
            print(f"✅ Current time ({current_hour}:00) is within active hours")
        else:
            print(f"⚠️  Current time ({current_hour}:00) is outside active hours")
            print("   Scheduler will wait until 7:00 AM to start creating videos")
        
        print("✅ Scheduler test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Scheduler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🚀 YouTube Automation Test Suite")
    print("=" * 50)
    
    # Test 1: Manual video creation
    print("TEST 1: Manual Video Creation")
    video_success = test_automation()
    
    # Test 2: Scheduler system
    print("\nTEST 2: Scheduler System")
    scheduler_success = test_scheduler()
    
    # Summary
    print("\n📊 TEST RESULTS")
    print("=" * 50)
    print(f"Video Creation: {'✅ PASS' if video_success else '❌ FAIL'}")
    print(f"Scheduler System: {'✅ PASS' if scheduler_success else '❌ FAIL'}")
    
    if video_success and scheduler_success:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Your automation system is ready to use")
        print("🚀 Run 'python start_automation.py' to start daily automation")
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("🔧 Please check the error messages above and fix any issues")
    
    return video_success and scheduler_success

if __name__ == "__main__":
    main()
