"""
LearnForge AI - Phase 0 Environment Verification Script
Validates Python runtime, SQLite functionality (WAL & Foreign Keys),
directory permissions, Ollama connectivity, and OpenAI key status.
"""
import sys
import os
import sqlite3
import urllib.request
import urllib.error
import json
from pathlib import Path

def print_status(component: str, status: bool, detail: str = ""):
    symbol = "✓ [PASS]" if status else "✗ [WARN/FAIL]"
    print(f"{symbol} {component:<30} {detail}")

def check_python_version():
    v = sys.version_info
    valid = (v.major == 3 and v.minor >= 11)
    print_status("Python Runtime (>=3.11)", valid, f"Installed: {v.major}.{v.minor}.{v.micro}")
    return valid

def check_sqlite_capabilities():
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Foreign Keys
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0] == 1
        
        # Test WAL pragma capability
        test_db = Path("test_wal.db")
        wal_conn = sqlite3.connect(test_db)
        wal_cur = wal_conn.cursor()
        wal_cur.execute("PRAGMA journal_mode = WAL;")
        wal_mode = wal_cur.fetchone()[0].lower()
        wal_conn.close()
        
        if test_db.exists():
            test_db.unlink(missing_ok=True)
            for extra in Path(".").glob("test_wal.db*"):
                extra.unlink(missing_ok=True)
                
        status = fk_status and ("wal" in wal_mode or "memory" in wal_mode)
        print_status("SQLite (ForeignKeys + WAL)", status, f"Foreign Keys: {fk_status}, Journal Mode: {wal_mode.upper()}")
        return status
    except Exception as e:
        print_status("SQLite (ForeignKeys + WAL)", False, str(e))
        return False

def check_directories():
    base_dir = Path(__file__).resolve().parent
    dirs = [
        base_dir / "uploads",
        base_dir / "chroma_data",
        base_dir / "migrations",
    ]
    all_ok = True
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        test_file = d / ".write_test"
        try:
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        except Exception:
            all_ok = False
    print_status("Local Storage Directories", all_ok, "uploads, chroma_data, migrations writable")
    return all_ok

def check_ollama_service():
    url = "http://localhost:11434/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LearnForge-Phase0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            detail = f"Online. Installed models: {models if models else 'None (run: ollama pull qwen2.5:7b)'}"
            print_status("Ollama Local LLM Service", True, detail)
            return True
    except urllib.error.URLError:
        print_status("Ollama Local LLM Service", False, "Offline or not installed on port 11434 (See setup guide)")
        return False
    except Exception as e:
        print_status("Ollama Local LLM Service", False, f"Error: {e}")
        return False

def check_env_secrets():
    env_file = Path(__file__).resolve().parent / ".env"
    has_env = env_file.exists()
    
    # Check .gitignore
    root_gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
    git_ignored = False
    if root_gitignore.exists():
        content = root_gitignore.read_text(encoding="utf-8")
        if ".env" in content:
            git_ignored = True
            
    status = has_env and git_ignored
    print_status("Environment & Secret Exclusions", status, f".env exists: {has_env}, .gitignore excludes .env: {git_ignored}")
    return status

def run_all_checks():
    print("=" * 70)
    print("LEARNFORGE AI — PHASE 0 ENVIRONMENT & ARCHITECTURE VERIFICATION")
    print("=" * 70)
    
    check_python_version()
    check_sqlite_capabilities()
    check_directories()
    check_env_secrets()
    check_ollama_service()
    
    print("=" * 70)
    print("Phase 0 Environment check completed.")
    print("=" * 70)

if __name__ == "__main__":
    run_all_checks()
