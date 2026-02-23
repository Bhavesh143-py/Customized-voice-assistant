@echo off
title PVG Voice Assistant - Re-ingesting Data
echo Re-ingesting college data...
echo (Run this whenever you add new .txt files to data\ folder)
docker compose run --rm ingester
echo Done! Restart with START.bat
pause
