#!/usr/bin/env bash
# Uruchomienie dashboardu: ./dashboard/start.sh
set -e
cd "$(dirname "$0")"
echo "==> Dashboard: http://127.0.0.1:8080"
python3 -m uvicorn app:app --host 127.0.0.1 --port 8080 --reload
