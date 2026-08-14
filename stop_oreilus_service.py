"""
O.R.E.I.L.U.S. Service Stopper
Stops the background service
"""
import os
import sys
import signal
from pathlib import Path
from datetime import datetime

# Paths
LOG_FILE = Path(r"C:\Users\Victoria\oreilus\oreilus_service.log")
PID_FILE = Path(r"C:\Users\Victoria\oreilus\oreilus.pid")


def log(message):
    """Log message to file"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")


def stop_service():
    """Stop O.R.E.I.L.U.S. background service"""
    try:
        if not PID_FILE.exists():
            log("No PID file found. Service may not be running.")
            print("[INFO] O.R.E.I.L.U.S. is not running (no PID file found)")
            return False

        # Read PID
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())

        log(f"Stopping O.R.E.I.L.U.S. service (PID: {pid})...")
        print(f"Stopping O.R.E.I.L.U.S. (PID: {pid})...")

        # Kill the process
        if sys.platform == 'win32':
            os.system(f"taskkill /F /PID {pid} /T")
        else:
            os.kill(pid, signal.SIGTERM)

        # Remove PID file
        PID_FILE.unlink()

        log("O.R.E.I.L.U.S. service stopped successfully")
        print("[SUCCESS] O.R.E.I.L.U.S. stopped successfully")
        return True

    except ProcessLookupError:
        log(f"Process {pid} not found. Removing stale PID file.")
        print(f"[INFO] Process not found. Cleaning up...")
        if PID_FILE.exists():
            PID_FILE.unlink()
        return False

    except Exception as e:
        log(f"ERROR: Failed to stop service - {e}")
        print(f"[FAILED] Failed to stop O.R.E.I.L.U.S.: {e}")
        return False


if __name__ == "__main__":
    stop_service()
