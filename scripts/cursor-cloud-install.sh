#!/usr/bin/env bash
set -euo pipefail

cd /workspace

if [ ! -d backend ] || [ ! -d frontend ]; then
  echo "backend/ and frontend/ are not present in this checkout; skipping app dependency install."
  echo "This is expected on the initial skeleton main branch. Switch to the Insightforge app branch to install dependencies."
  exit 0
fi

echo "Installing Insightforge backend dependencies..."
cd backend
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -e ".[dev]"

echo "Installing Insightforge frontend dependencies..."
cd ../frontend
npm ci

echo "Insightforge Cursor Cloud install complete."
