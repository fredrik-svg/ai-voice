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

echo "=================================================="
echo "Raspberry Pi 5 + ReSpeaker USB 4-Mic Array Setup"
echo "=================================================="
echo ""
echo "This script will install dependencies for:"
echo "  - Raspberry Pi 5"
echo "  - ReSpeaker USB 4-Mic Array (USB audio device)"
echo ""

# Note: No I2S configuration needed for USB audio devices
echo "Updating package lists..."
retry_command sudo apt-get update

echo "Installing system packages..."
retry_command sudo apt-get install -y \
  python3 python3-pip python3-dev python3-venv \
  git alsa-utils sox libasound2-dev

# Install RPi.GPIO for Raspberry Pi 5
# Note: RPi.GPIO works on Pi 5, but lgpio is recommended for newer projects
echo "Installing GPIO support..."
retry_command sudo apt-get install -y python3-rpi.gpio

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

echo ""
echo "=================================================="
echo "USB Audio Device Detection"
echo "=================================================="
echo ""
echo "Checking for USB audio devices..."
if arecord -l | grep -i "usb\|respeaker"; then
  echo ""
  echo "✓ USB audio device detected!"
  echo ""
  echo "Note the card number and device number above."
  echo "Example: card 1, device 0 -> use 'plughw:1,0' in config"
  echo "Or use: 'plughw:CARD=ArrayUAC10,DEV=0' for name-based addressing"
else
  echo ""
  echo "⚠ No USB audio device detected yet."
  echo "Please connect your ReSpeaker USB 4-Mic Array and run:"
  echo "  arecord -l"
  echo "to verify the device is recognized."
fi

echo ""
echo "=================================================="
echo "Installation Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Copy the Pi5-specific config:"
echo "   cp config.pi5-usb.example.yaml config.yaml"
echo ""
echo "2. Edit config.yaml with your MQTT broker settings"
echo ""
echo "3. Verify your USB audio device with:"
echo "   arecord -l"
echo ""
echo "4. Test audio capture (6 channels, 16kHz):"
echo "   arecord -D plughw:CARD=ArrayUAC10,DEV=0 -c 6 -f S16_LE -r 16000 -d 3 test.wav"
echo "   aplay test.wav"
echo ""
echo "5. Run the voice agent:"
echo "   ./scripts/run.sh"
echo ""
