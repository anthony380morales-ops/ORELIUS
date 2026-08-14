"""
O.R.E.I.L.U.S. Service Starter
Runs the backend as a background service
"""
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# Paths
BACKEND_DIR = Path(r"C:\Users\Victoria\oreilus\backend")
VENV_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
LOG_FILE = Path(r"C:\Users\Victoria\oreilus\oreilus_service.log")
PID_FILE = Path(r"C:\Users\Victoria\oreilus\oreilus.pid")


def log(message):
    """Log message to file"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")


def start_service():
    """Start O.R.E.I.L.U.S. as a background service"""
    try:
        log("Starting O.R.E.I.L.U.S. backend service...")

        # Check if already running
        if PID_FILE.exists():
            with open(PID_FILE, 'r') as f:
                old_pid = f.read().strip()
            log(f"Warning: PID file exists (PID: {old_pid}). Service may already be running.")

        # Start uvicorn in background
        process = subprocess.Popen(
            [
                str(VENV_PYTHON),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
            ],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        # Save PID
        with open(PID_FILE, 'w') as f:
            f.write(str(process.pid))

        log(f"O.R.E.I.L.U.S. backend started successfully (PID: {process.pid})")
        log(f"Backend running at: http://localhost:8000")
        log(f"Automation scheduled: 7 AM (Content) and 8 AM (Intel) PST")
        print(f"[SUCCESS] O.R.E.I.L.U.S. started successfully (PID: {process.pid})")
        print(f"  Backend: http://localhost:8000")
        print(f"  Logs: {LOG_FILE}")
        print(f"  Run 'python stop_oreilus_service.py' to stop")

        return True

    except Exception as e:
        log(f"ERROR: Failed to start service - {e}")
        print(f"[FAILED] Failed to start O.R.E.I.L.U.S.: {e}")
        return False


if __name__ == "__main__":
    start_service()
