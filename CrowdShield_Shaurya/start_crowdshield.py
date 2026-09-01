"""
CrowdShield Unified Launcher Script
====================================
Launches all CrowdShield services together:
1. Camera Analytics Backend (Port 8765) - YOLO11 Detection, Risk Engine & Stream
2. Location Aggregator Backend (Port 8766) - Geographic Heatmap & Privacy Engine
3. Vite React Frontend (Port 5173) - Multi-role Dashboard UI
"""

import os
import sys
import subprocess
import time
import threading
import shutil

_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_DIR, "src")
_FRONTEND_DIR = os.path.join(_DIR, "frontend")

# Portable Node/NPM runtime environment helper
def _ensure_node_path():
    if shutil.which("npm") or shutil.which("npm.cmd"):
        return
    candidates = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        os.path.expanduser(r"~\AppData\Roaming\npm"),
        os.path.expanduser(r"~\AppData\Local\Programs\node"),
        os.path.expanduser(r"~\AppData\Local\OpenAI\Codex\runtimes\cua_node\1b23c930bdf84ed6\bin"),
    ]
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata and os.path.exists(local_appdata):
        for root, dirs, files in os.walk(local_appdata):
            if "npm.cmd" in files or "npm" in files:
                candidates.append(root)
                break
    for p in candidates:
        if os.path.exists(p) and (os.path.exists(os.path.join(p, "npm.cmd")) or os.path.exists(os.path.join(p, "npm"))):
            os.environ["PATH"] = p + os.path.pathsep + os.environ.get("PATH", "")
            break

_ensure_node_path()

def run_camera_backend():
    detect_script = os.path.join(_SRC_DIR, "detection", "detect.py")
    print(" [1/3] Starting Camera Analytics Server (Port 8765)...")
    subprocess.run([sys.executable, detect_script], cwd=_DIR)

def run_location_backend():
    location_script = os.path.join(_SRC_DIR, "location", "location_server.py")
    print(" [2/3] Starting Location Heatmap Server (Port 8766)...")
    subprocess.run([sys.executable, location_script], cwd=_DIR)

def run_frontend():
    print(" [3/3] Starting Vite Frontend Server (Port 5173)...")
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    subprocess.run([npm_cmd, "run", "dev"], cwd=_FRONTEND_DIR, shell=True)

if __name__ == "__main__":
    print("=" * 65)
    print("               CROWDSHIELD SYSTEM LAUNCHER                 ")
    print("=====================================================")
    print(" Starting all services...")
    print("  - Camera Backend:   http://127.0.0.1:8765")
    print("  - Location Backend: http://127.0.0.1:8766")
    print("  - Frontend UI:      http://localhost:5173")
    print("=" * 65)

    # Start Backends in background threads
    t_cam = threading.Thread(target=run_camera_backend, daemon=True)
    t_loc = threading.Thread(target=run_location_backend, daemon=True)
    t_cam.start()
    t_loc.start()

    time.sleep(2)

    print("\n -> Backends live! Launching Frontend Dashboard...\n")
    try:
        run_frontend()
    except KeyboardInterrupt:
        print("\n Shutting down CrowdShield services.")
