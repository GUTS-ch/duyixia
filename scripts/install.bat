@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title DuYiXia Setup
where python >nul 2>&1
if errorlevel 1 (
  py -3 -X utf8 scripts\install.py
) else (
  python -X utf8 scripts\install.py
)
if errorlevel 1 pause
