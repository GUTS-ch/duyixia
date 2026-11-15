@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title DuYiXia - run from source
where python >nul 2>&1
if errorlevel 1 (
  echo Python 3.10+ not found. Please install Python first.
  pause
  exit /b 1
)
echo Installing dependencies ...
python -X utf8 -m pip install -q -r requirements.txt
python -X utf8 scripts\prepare_assets.py
start "" pythonw app\main.py
