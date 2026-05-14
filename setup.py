#!/bin/bash

set -e

echo "========================================"
echo " ISP Scrubbing Validation Setup"
echo "========================================"

echo
echo "[*] Updating packages..."

sudo apt update

echo
echo "[*] Installing dependencies..."

sudo apt install -y \
    python3 \
    python3-pip \
    htop \
    iftop \
    net-tools \
    curl

echo
echo "[*] Installing Python requirements..."

pip3 install -r requirements.txt

echo
echo "[+] Setup completed."

echo
echo "Useful monitoring commands:"
echo
echo "htop"
echo "sudo iftop"
echo "ss -s"
echo "netstat -ant | wc -l"

echo
echo "Run the validator:"
echo
echo "python3 validator.py"