#!/usr/bin/env python3
import os
import sys
import socket

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, "dos-sim", "bin", "python")

# ── Validate venv exists ──────────────────────────────────────
if not os.path.exists(VENV_PYTHON):
    print()
    print("[!] Virtual environment not found.")
    print("    Run setup first:")
    print()
    print("      sudo bash setup.py")
    print()
    sys.exit(1)

# ── Re-exec with venv Python if needed ───────────────────────
if os.path.abspath(sys.executable) != os.path.abspath(VENV_PYTHON):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

# ── Everything below runs inside the venv ────────────────────

try:
    import uvicorn
except ImportError:
    print()
    print("[!] Dependencies missing. Re-run setup:")
    print()
    print("      sudo bash setup.py")
    print()
    sys.exit(1)

HOST = "0.0.0.0"
PORT = 8000


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


lan_ip = get_lan_ip()

print()
print("=" * 54)
print("  ISP SCRUBBING VALIDATOR")
print("=" * 54)
print()
print("  Dashboard URL:")
print(f"    http://localhost:{PORT}")
print(f"    http://{lan_ip}:{PORT}   <- share this with the client")
print()
print("  Press Ctrl+C to stop.")
print("=" * 54)
print()

os.chdir(SCRIPT_DIR)
uvicorn.run("server:app", host=HOST, port=PORT, reload=False)
