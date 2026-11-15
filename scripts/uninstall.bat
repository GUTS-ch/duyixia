@echo off
chcp 65001 >nul
title DuYiXia Uninstall
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v LingoRead /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v 读一下 /f >nul 2>&1
if exist "%USERPROFILE%\Desktop\LingoRead.lnk" del "%USERPROFILE%\Desktop\LingoRead.lnk" >nul 2>&1
if exist "%USERPROFILE%\Desktop\读一下.lnk" del "%USERPROFILE%\Desktop\读一下.lnk" >nul 2>&1
if exist "%USERPROFILE%\OneDrive\Desktop\LingoRead.lnk" del "%USERPROFILE%\OneDrive\Desktop\LingoRead.lnk" >nul 2>&1
if exist "%USERPROFILE%\OneDrive\Desktop\读一下.lnk" del "%USERPROFILE%\OneDrive\Desktop\读一下.lnk" >nul 2>&1
echo Autostart entry and shortcuts removed.
echo Program folder is kept. Remove it manually if needed:
echo   %~dp0
echo.
pause
