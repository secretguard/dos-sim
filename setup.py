#!/bin/bash

set -e

echo "========================================"
echo " ISP Scrubbing Validation Setup"
echo "========================================"

VENV_NAME="dos-sim"
VENV_PATH="./$VENV_NAME"

echo
echo "[*] Updating packages..."
sudo apt update -qq

echo
echo "[*] Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    htop \
    iftop \
    net-tools \
    curl

echo
echo "[*] Creating virtual environment ($VENV_NAME)..."
python3 -m venv "$VENV_PATH"

echo
echo "[*] Installing Python requirements inside venv..."
"$VENV_PATH/bin/pip" install --quiet --upgrade pip
"$VENV_PATH/bin/pip" install --quiet -r requirements.txt

echo
echo "========================================"
echo " Setup complete."
echo "========================================"
echo
echo " To start the dashboard, run:"
echo
echo "   python3 start.py"
echo
