"""
Database Backup and Restoration Utility for LearnForge AI.
Demonstrates local SQLite backup, WAL checkpointing, and integrity checks.
"""

import os
import sys
import sqlite3
import argparse
import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BACKEND_DIR / "learnforge.db"
DEFAULT_BACKUP_DIR = BACKEND_DIR / "backups"


def perform_backup(db_path: Path = DEFAULT_DB_PATH, backup_dir: Path = DEFAULT_BACKUP_DIR) -> Path:
    """
    Safely creates a consistent online backup of the SQLite database.
    Performs a WAL checkpoint to flush uncommitted WAL pages into the database file,
    then executes an online backup using sqlite3.Connection.backup().
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found at {db_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"learnforge_backup_{timestamp}.db"

    source_conn = sqlite3.connect(str(db_path))
    try:
        # Checkpoint WAL before backup to ensure complete synchronization
        source_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        dest_conn = sqlite3.connect(str(backup_file))
        try:
            # Atomic online SQLite backup
            source_conn.backup(dest_conn, pages=100)
            print(f"[OK] Database successfully backed up to: {backup_file}")
        finally:
            dest_conn.close()
    finally:
        source_conn.close()

    # Verify backup integrity
    verify_conn = sqlite3.connect(str(backup_file))
    try:
        cursor = verify_conn.cursor()
        quick_check = cursor.execute("PRAGMA quick_check;").fetchone()
        fk_check = cursor.execute("PRAGMA foreign_key_check;").fetchall()

        if quick_check and quick_check[0] == "ok" and len(fk_check) == 0:
            print("[OK] Backup integrity check PASSED (clean SQLite quick_check & zero FK violations)")
        else:
            raise RuntimeError(f"Backup verification failed: quick_check={quick_check}, fk_violations={fk_check}")
    finally:
        verify_conn.close()

    return backup_file


def perform_restore(backup_path: Path, target_db_path: Path = DEFAULT_DB_PATH):
    """
    Safely restores the SQLite database from a verified backup file.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found at {backup_path}")

    # Verify integrity of backup file before restoring
    test_conn = sqlite3.connect(str(backup_path))
    try:
        cursor = test_conn.cursor()
        quick_check = cursor.execute("PRAGMA quick_check;").fetchone()
        if not quick_check or quick_check[0] != "ok":
            raise RuntimeError("Cannot restore: Backup file fails integrity check.")
    finally:
        test_conn.close()

    source_conn = sqlite3.connect(str(backup_path))
    dest_conn = sqlite3.connect(str(target_db_path))
    try:
        source_conn.backup(dest_conn)
        print(f"[OK] Database restored from {backup_path} to {target_db_path}")
    finally:
        dest_conn.close()
        source_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LearnForge AI SQLite Backup & Restore")
    parser.add_argument("--action", choices=["backup", "restore"], default="backup", help="Action to perform")
    parser.add_argument("--source", type=str, default="", help="Source backup file path for restoration")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB_PATH), help="Target database path")

    args = parser.parse_args()

    db_p = Path(args.db)
    if args.action == "backup":
        perform_backup(db_path=db_p)
    elif args.action == "restore":
        if not args.source:
            print("Error: --source <backup_file_path> is required for restore action.")
            sys.exit(1)
        perform_restore(backup_path=Path(args.source), target_db_path=db_p)
