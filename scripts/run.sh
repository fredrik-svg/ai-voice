#!/usr/bin/env bash
set -euo pipefail

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
else
  echo "Warning: Virtual environment not found at venv/bin/activate"
  echo "Please run './scripts/install_deps.sh' first to create it."
  exit 1
fi

python3 -m src.agent config.yaml
