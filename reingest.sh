#!/bin/bash
# ── Re-ingest data (run when you add new .txt files) ─────────────────────────
echo "Re-ingesting college data..."
docker compose run --rm ingester
echo "Done! Restart with ./start.sh"
