@echo off
title CrowdShield Launcher
echo Starting CrowdShield Platform...
cd /d "%~dp0CrowdShield_Shaurya"
..\venv\Scripts\python.exe start_crowdshield.py
pause
