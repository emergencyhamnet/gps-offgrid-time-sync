@echo off
REM ============================================
REM GPS Off-Grid Time Sync Launcher
REM ============================================

cd /d C:\gps_time

echo.
echo Running GPS Time Sync...
echo.

python gps_time_sync.py COM10 --warn 0.35 --sync-threshold 0.75

echo.
echo ============================================
echo Press any key to close this window...
pause >nul