#!/bin/bash
# ── PVG Voice Assistant — Start (Linux) ──────────────────────────────────────
echo "Starting PVG Voice Assistant..."
docker compose up -d
sleep 4
echo "Open http://localhost:3000 in Chrome/Firefox"
