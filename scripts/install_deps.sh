#!/usr/bin/env bash
set -euo pipefail

# Configuration for retry and timeout settings
readonly MAX_RETRY_ATTEMPTS=5
readonly PIP_RETRIES=5
readonly PIP_TIMEOUT=60

# Function to retry a command with exponential backoff
retry_command() {
  local max_attempts=$MAX_RETRY_ATTEMPTS
  local timeout=1
  local attempt=1
  local exit_code=0

  while [ $attempt -le $max_attempts ]; do
    if "$@"; then
      return 0
    else
      exit_code=$?
      if [ $attempt -lt $max_attempts ]; then
        echo "Command failed (attempt $attempt/$max_attempts). Retrying in ${timeout}s..." >&2
        sleep $timeout
        timeout=$((timeout * 2))
        attempt=$((attempt + 1))
      else
        echo "Command failed after $max_attempts attempts." >&2
        return $exit_code
      fi
    fi
  done
  
  # This line should never be reached, but provides a safe fallback
  return $exit_code
}

# Enable I2S (requires reboot afterwards)
if [ -f /boot/firmware/config.txt ] && ! grep -q '^dtparam=i2s=on' /boot/firmware/config.txt; then
  echo 'dtparam=i2s=on' | sudo tee -a /boot/firmware/config.txt
  echo "I2S enabled (dtparam=i2s=on). Reboot required for codec to appear."
fi

echo "Updating package lists..."
retry_command sudo apt-get update

echo "Installing system packages..."
retry_command sudo apt-get install -y \
  python3 python3-pip python3-dev python3-venv \
  git alsa-utils sox libasound2-dev

# Check and add user to audio group
echo "Checking audio group membership..."
if ! groups | grep -q '\baudio\b'; then
  echo "Adding user '$(whoami)' to 'audio' group for audio device access..."
  sudo usermod -a -G audio "$(whoami)"
  echo ""
  echo "=============================================="
  echo "IMPORTANT: Audio group membership updated!"
  echo "=============================================="
  echo "You have been added to the 'audio' group."
  echo "You MUST log out and log back in (or reboot) for this to take effect."
  echo "After logging back in, verify with: groups"
  echo "You should see 'audio' in the list."
  echo "=============================================="
  echo ""
else
  echo "✓ User is already in 'audio' group"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
  
  # Verify venv was created successfully
  if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Failed to create virtual environment!" >&2
    echo "The venv directory exists but venv/bin/activate was not created." >&2
    exit 1
  fi
  echo "✓ Virtual environment created successfully"
else
  echo "✓ Virtual environment already exists"
fi

# Activate virtual environment and install Python dependencies
echo "Installing Python dependencies in virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
retry_command python3 -m pip install --retries $PIP_RETRIES --timeout $PIP_TIMEOUT --upgrade pip

echo "Installing dependencies from requirements.txt..."
retry_command python3 -m pip install --retries $PIP_RETRIES --timeout $PIP_TIMEOUT -r requirements.txt

deactivate || true

echo "Done. Next: configure WM8960 driver per HAT-guide, then set ALSA device in config.yaml (e.g., plughw:1,0)."
