"""
LearnForge AI — Unified Dual-Server Runner
Runs both FastAPI backend (port 8000) and Vite React frontend (port 5173) concurrently.
Terminates both cleanly on Ctrl+C.
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

# Virtual environment python binary
if sys.platform == "win32":
    PYTHON_BIN = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
    NPM_CMD = "npm.cmd"
else:
    PYTHON_BIN = BACKEND_DIR / "venv" / "bin" / "python"
    NPM_CMD = "npm"

if not PYTHON_BIN.exists():
    # Fallback to system python if venv not found
    PYTHON_BIN = Path(sys.executable)

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_BOLD = "\033[1m"


def stream_output(process, prefix, color):
    """Streams stdout/stderr with a colored prefix."""
    try:
        for line in iter(process.stdout.readline, ""):
            if not line:
                break
            sys.stdout.write(f"{color}{prefix}{COLOR_RESET} {line}")
            sys.stdout.flush()
    except Exception:
        pass


def ensure_ollama():
    """Checks if Ollama is running, attempts to start it if installed locally."""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=1.5):
            print(f"{COLOR_GREEN}[Ollama]{COLOR_RESET}   Local AI engine is running on port 11434.")
            return None
    except Exception:
        pass

    # Check for local ollama executable
    ollama_path = None
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        candidate = Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.exists():
            ollama_path = str(candidate)

    if not ollama_path:
        import shutil
        ollama_path = shutil.which("ollama")

    if ollama_path:
        print(f"{COLOR_YELLOW}[Ollama]{COLOR_RESET}   Starting Ollama server...")
        try:
            creation_flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
            ollama_proc = subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
            time.sleep(2)
            print(f"{COLOR_GREEN}[Ollama]{COLOR_RESET}   Ollama server started successfully.")
            return ollama_proc
        except Exception as e:
            print(f"{COLOR_YELLOW}[Ollama]{COLOR_RESET}   Could not auto-start Ollama: {e}")
    else:
        print(f"{COLOR_YELLOW}[Ollama]{COLOR_RESET}   Ollama not detected (running in fallback/cloud mode).")
    return None


def main():
    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}===================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_YELLOW}       🚀 Starting LearnForge AI Platform           {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_YELLOW}===================================================={COLOR_RESET}\n")
    print(f"{COLOR_CYAN}[Backend]{COLOR_RESET}  FastAPI -> http://localhost:8000 (Swagger: /docs)")
    print(f"{COLOR_GREEN}[Frontend]{COLOR_RESET} Vite UI -> http://localhost:5173\n")
    print(f"Press {COLOR_BOLD}Ctrl+C{COLOR_RESET} to shut down both servers.\n")

    # Command for backend
    backend_cmd = [
        str(PYTHON_BIN),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
    ]

    # Command for frontend
    frontend_cmd = [NPM_CMD, "run", "dev"]

    processes = []

    try:
        # Check / start Ollama if available
        ollama_proc = ensure_ollama()
        if ollama_proc:
            processes.append(("Ollama", ollama_proc))

        # Start Backend
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )
        processes.append(("Backend", backend_proc))

        # Start Frontend
        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            shell=(sys.platform == "win32"),
            env=os.environ.copy(),
        )
        processes.append(("Frontend", frontend_proc))

        # Threads for streaming output
        t_back = threading.Thread(
            target=stream_output,
            args=(backend_proc, "[Backend] ", COLOR_CYAN),
            daemon=True,
        )
        t_front = threading.Thread(
            target=stream_output,
            args=(frontend_proc, "[Frontend]", COLOR_GREEN),
            daemon=True,
        )

        t_back.start()
        t_front.start()

        # Keep main thread alive
        while True:
            time.sleep(0.5)
            # Check if any process terminated unexpectedly
            for name, proc in processes:
                poll = proc.poll()
                if poll is not None:
                    print(f"\n{COLOR_RED}[WARNING] {name} exited with code {poll}{COLOR_RESET}")
                    return

    except KeyboardInterrupt:
        print(f"\n\n{COLOR_YELLOW}Shutting down LearnForge AI servers...{COLOR_RESET}")
    finally:
        for name, proc in processes:
            try:
                if proc.poll() is None:
                    if sys.platform == "win32":
                        # Terminate entire process tree on Windows
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        proc.terminate()
            except Exception:
                pass
        print(f"{COLOR_GREEN}✓ Both servers stopped cleanly.{COLOR_RESET}\n")


if __name__ == "__main__":
    main()
