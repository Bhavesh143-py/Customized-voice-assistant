@echo off
title PVG Voice Assistant - First Time Setup
color 1F

echo ==================================================
echo   PVG Voice Assistant - First Time Setup (Windows)
echo ==================================================

REM ── Check Docker ─────────────────────────────────────────────────────────
echo.
echo [1/5] Checking Docker...
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker not found!
    echo Download Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Docker Desktop is not running!
    echo Open Docker Desktop from Start Menu and wait for it to start.
    pause
    exit /b 1
)
echo Docker is running.

REM ── Check data folder ─────────────────────────────────────────────────────
echo.
echo [2/5] Checking data folder...
IF NOT EXIST "data\" (
    mkdir data
    echo Created data\ folder.
    echo Add your .txt college files to data\ then run this again.
    pause
    exit /b 1
)
set /a count=0
for %%f in (data\*.txt) do set /a count+=1
IF %count% EQU 0 (
    echo No .txt files found in data\ !
    echo Add your scraped college .txt files to data\ then run again.
    pause
    exit /b 1
)
echo Found %count% .txt files in data\.

REM ── Download TTS model ────────────────────────────────────────────────────
echo.
echo [3/5] Checking TTS model...
IF NOT EXIST "tts_models\" mkdir tts_models
IF NOT EXIST "tts_models\en_US-amy-medium.onnx" (
    echo Downloading Amy voice model (about 60MB)...
    curl -L --progress-bar -o tts_models\en_US-amy-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
    curl -L -o tts_models\en_US-amy-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
    echo Amy voice model downloaded.
) ELSE (
    echo Amy voice model already present.
)

REM ── Build and start ───────────────────────────────────────────────────────
echo.
echo [4/5] Building and starting all services...
echo First time takes 10-20 minutes - downloading Docker images and AI models.
docker compose up -d --build

REM ── Done ──────────────────────────────────────────────────────────────────
echo.
echo [5/5] Waiting for services to start...
timeout /t 10 /nobreak >nul

echo.
echo ==================================================
echo   Setup Complete!
echo   Open in browser: http://localhost:3000
echo   To start daily: double-click START.bat
echo ==================================================
pause
