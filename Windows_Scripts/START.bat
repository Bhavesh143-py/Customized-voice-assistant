@echo off
title PVG Voice Assistant - Starting
color 1F

echo Starting PVG Voice Assistant...

docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker Desktop is not running!
    echo Open Docker Desktop from Start Menu and wait for it to start.
    pause
    exit /b 1
)

docker compose up -d
timeout /t 5 /nobreak >nul

echo.
echo ==================================================
echo   PVG Voice Assistant is running!
echo   Open: http://localhost:3000
echo ==================================================
echo   PVG Admin Dashboard is Running!
echo   Open: http://localhost:3001
echo   To stop: double-click STOP.bat
echo ==================================================

start http://localhost:3000
pause
