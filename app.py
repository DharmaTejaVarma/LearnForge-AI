"""
LearnForge AI — Single-Command Setup & Launcher
Installs missing backend (Python) and frontend (Node.js) dependencies,
ensures backend/.env exists, and starts both FastAPI and Vite servers.

Usage:
    python -m app.py
    python app.py
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def _resolve_python_bin() -> Path:
    if sys.platform == "win32":
        venv_py = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
    else:
        venv_py = BACKEND_DIR / "venv" / "bin" / "python"
    return venv_py if venv_py.exists() else Path(sys.executable)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else ""


def ensure_backend_dependencies(python_bin: Path, force: bool = False) -> None:
    req_file = BACKEND_DIR / "requirements.txt"
    stamp_file = BACKEND_DIR / ".deps_installed"
    if not req_file.exists():
        return

    req_hash = _file_sha256(req_file)
    already_stamped = stamp_file.exists() and stamp_file.read_text(encoding="utf-8").strip() == req_hash

    if not force and already_stamped:
        # Quick sanity check that core imports are actually available in this Python
        chk = subprocess.run(
            [str(python_bin), "-c", "import fastapi, uvicorn, sqlalchemy, chromadb, openai"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if chk.returncode == 0:
            print("[Setup]    Backend Python dependencies already up to date.")
            return

    print("[Setup]    Installing backend Python dependencies (backend/requirements.txt)...")
    subprocess.check_call([str(python_bin), "-m", "pip", "install", "-r", str(req_file)])
    stamp_file.write_text(req_hash, encoding="utf-8")
    print("[Setup]    Backend Python dependencies installed.")


def ensure_frontend_dependencies(force: bool = False) -> None:
    pkg_file = FRONTEND_DIR / "package.json"
    node_modules = FRONTEND_DIR / "node_modules"
    stamp_file = FRONTEND_DIR / ".deps_installed"
    if not pkg_file.exists():
        return

    pkg_hash = _file_sha256(pkg_file)
    already_stamped = (
        node_modules.exists()
        and stamp_file.exists()
        and stamp_file.read_text(encoding="utf-8").strip() == pkg_hash
    )
    if not force and already_stamped:
        print("[Setup]    Frontend Node dependencies already up to date.")
        return

    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(npm_cmd) is None:
        raise RuntimeError("npm was not found on PATH. Please install Node.js (v18+) and retry.")

    print("[Setup]    Installing frontend Node dependencies (frontend/package.json)...")
    subprocess.check_call([npm_cmd, "install"], cwd=str(FRONTEND_DIR))
    stamp_file.write_text(pkg_hash, encoding="utf-8")
    print("[Setup]    Frontend Node dependencies installed.")


def ensure_env_file() -> None:
    env_file = BACKEND_DIR / ".env"
    example_file = BACKEND_DIR / ".env.example"
    if not env_file.exists() and example_file.exists():
        shutil.copy2(example_file, env_file)
        print("[Setup]    Created backend/.env from backend/.env.example.")


def main() -> None:
    force_install = "--reinstall" in sys.argv
    if force_install:
        sys.argv = [a for a in sys.argv if a != "--reinstall"]

    python_bin = _resolve_python_bin()
    ensure_env_file()
    ensure_backend_dependencies(python_bin, force=force_install)
    ensure_frontend_dependencies(force=force_install)

    # Delegate server startup to run_servers.py so behavior is 100% identical
    import run_servers

    run_servers.main()


if __name__ == "__main__":
    main()
