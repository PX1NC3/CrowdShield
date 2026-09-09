@echo off
title CrowdShield Launcher
echo Starting CrowdShield Platform...
cd /d "%~dp0"
venv\Scripts\python.exe start_crowdshield.py
pause
