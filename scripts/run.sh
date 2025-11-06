#!/usr/bin/env bash
set -euo pipefail

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

python3 -m src.agent config.yaml
