@echo off
setlocal

REM Prefer Python 3.12 for discord.py compatibility (audioop issue on 3.13).
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.12 not found.
  echo Please install Python 3.12, then run this file again.
  pause
  exit /b 1
)

py -3.12 -m pip install -U -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install requirements.
  pause
  exit /b 1
)

cls
py -3.12 bot.py
pause