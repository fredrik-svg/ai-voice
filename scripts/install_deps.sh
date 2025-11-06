#!/usr/bin/env bash
set -euo pipefail

# Enable I2S (requires reboot afterwards)
if [ -f /boot/firmware/config.txt ] && ! grep -q '^dtparam=i2s=on' /boot/firmware/config.txt; then
  echo 'dtparam=i2s=on' | sudo tee -a /boot/firmware/config.txt
  echo "I2S enabled (dtparam=i2s=on). Reboot required for codec to appear."
fi

sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-dev python3-venv git alsa-utils sox libasound2-dev

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Activate virtual environment and install Python dependencies
echo "Installing Python dependencies in virtual environment..."
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
deactivate

echo "Done. Next: configure WM8960 driver per HAT-guide, then set ALSA device in config.yaml (e.g., plughw:1,0)."
