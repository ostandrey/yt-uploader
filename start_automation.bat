@echo off
echo Starting YouTube Automation...
echo.

REM Activate conda environment
call conda activate yt-auto-uploader

REM Run the automation launcher
python start_automation.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Press any key to close...
    pause >nul
)
