"""
LearnForge AI — Unified Dual-Server Runner
Runs both FastAPI backend (default port 8000) and Vite React frontend (default port 5173) concurrently.
Detects occupied ports automatically and falls back cleanly while keeping CORS and Vite proxy aligned.
Terminates both cleanly on Ctrl+C.
"""

import argparse
import json
import os
import re
import socket
import sys
import time
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


def is_port_in_use(port: int) -> bool:
    """Checks whether a port is already bound or listening on IPv4 or IPv6 loopback."""
    targets = [(socket.AF_INET, "127.0.0.1")]
    if socket.has_ipv6:
        targets.append((socket.AF_INET6, "::1"))

    for family, host in targets:
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.25)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            pass

    # Verify we can actually bind IPv4 127.0.0.1 (catches WinError 10048/10013)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", port))
    except OSError:
        return True

    return False


def get_port_owner_pid(port: int) -> str | None:
    """Best-effort lookup of the PID listening on the given port (Windows)."""
    if sys.platform != "win32":
        return None
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        pattern = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE)
        for line in out.splitlines():
            match = pattern.match(line)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def resolve_port(preferred: int, label: str, exclude: set[int] | None = None) -> int:
    """Returns preferred port if free, otherwise finds the next open port and warns clearly."""
    excluded = exclude or set()
    if preferred not in excluded and not is_port_in_use(preferred):
        return preferred

    owner_pid = get_port_owner_pid(preferred)
    pid_info = f" (PID {owner_pid})" if owner_pid else ""

    for candidate in range(preferred + 1, preferred + 50):
        if candidate not in excluded and not is_port_in_use(candidate):
            print(
                f"{COLOR_YELLOW}[PORT]{COLOR_RESET}     Port {preferred} is already in use{pid_info}. "
                f"Starting {label} on port {candidate} instead."
            )
            return candidate

    raise RuntimeError(f"Could not find an available port near {preferred} for {label}.")


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
    parser = argparse.ArgumentParser(description="LearnForge AI Unified Dual-Server Runner")
    parser.add_argument("--backend-port", type=int, default=8000, help="Preferred FastAPI port (default: 8000)")
    parser.add_argument("--frontend-port", type=int, default=5173, help="Preferred Vite UI port (default: 5173)")
    args = parser.parse_args()

    print(f"\n{COLOR_BOLD}{COLOR_YELLOW}===================================================={COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_YELLOW}       🚀 Starting LearnForge AI Platform           {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_YELLOW}===================================================={COLOR_RESET}\n")

    backend_port = resolve_port(args.backend_port, "FastAPI Backend")
    frontend_port = resolve_port(args.frontend_port, "Vite Frontend", exclude={backend_port})

    print(f"{COLOR_CYAN}[Backend]{COLOR_RESET}  FastAPI -> http://127.0.0.1:{backend_port} (Swagger: /docs)")
    print(f"{COLOR_GREEN}[Frontend]{COLOR_RESET} Vite UI -> http://127.0.0.1:{frontend_port}\n")
    print(f"Press {COLOR_BOLD}Ctrl+C{COLOR_RESET} to shut down both servers.\n")

    # Command for backend — no reload so background lesson generation tasks aren't interrupted
    # (Hot-reload kills asyncio tasks including the lesson generation background workers)
    backend_cmd = [
        str(PYTHON_BIN),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(backend_port),
        "--workers",
        "1",
    ]

    backend_env = os.environ.copy()
    backend_env["CORS_ORIGINS"] = json.dumps([
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}",
        "http://localhost:3000",
    ])

    # Command for frontend
    frontend_cmd = [NPM_CMD, "run", "dev"]
    frontend_env = os.environ.copy()
    frontend_env["VITE_PORT"] = str(frontend_port)
    frontend_env["VITE_API_BASE_URL"] = f"http://127.0.0.1:{backend_port}/api/v1"
    frontend_env["VITE_API_PROXY_TARGET"] = f"http://127.0.0.1:{backend_port}"

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
            env=backend_env,
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
            env=frontend_env,
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
