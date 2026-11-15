@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title DuYiXia Build
python -X utf8 scripts\build.py
if errorlevel 1 pause
