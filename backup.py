"""
backup.py — Digital Shadow SQLite backup utility.
Creates timestamped backup copies of the database in the backups/ directory.
Run manually or schedule with: python backup.py

Usage:
    python backup.py                      # backup now
    python backup.py --verify             # backup + integrity check
    python backup.py --restore <file>     # restore from backup
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "digital_shadow.db"
BACKUP_DIR = PROJECT_ROOT / "backups"
MAX_BACKUPS = 14          # keep up to 14 daily backups
BACKUP_PREFIX = "digital_shadow_backup_"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")


def create_backup() -> Path:
    """Create a timestamped backup of the SQLite database.
    Uses SQLite online backup API for a consistent snapshot."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        print(f"[WARN] Database not found at {DB_PATH} — nothing to backup.")
        return None

    dest = BACKUP_DIR / f"{BACKUP_PREFIX}{_timestamp()}.db"

    # SQLite online backup API — safe to run while the DB is open
    src_conn = sqlite3.connect(str(DB_PATH))
    dst_conn = sqlite3.connect(str(dest))
    try:
        with dst_conn:
            src_conn.backup(dst_conn, pages=256)
    finally:
        src_conn.close()
        dst_conn.close()

    size_kb = dest.stat().st_size // 1024
    print(f"[OK] Backup created: {dest.name} ({size_kb} KB)")
    return dest


def verify_backup(backup_path: Path) -> bool:
    """Run SQLite integrity check on a backup file."""
    conn = sqlite3.connect(str(backup_path))
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        ok = result[0] == "ok"
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] Integrity check: {backup_path.name} — {result[0]}")
        return ok
    finally:
        conn.close()


def rotate_backups():
    """Remove oldest backups beyond MAX_BACKUPS."""
    backups = sorted(BACKUP_DIR.glob(f"{BACKUP_PREFIX}*.db"))
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        oldest.unlink()
        print(f"[INFO] Rotated out old backup: {oldest.name}")


def restore_backup(source: Path):
    """Restore a backup to the live database path.
    Creates a safety copy of the current DB before overwriting."""
    if not source.exists():
        print(f"[ERROR] Backup file not found: {source}")
        sys.exit(1)

    # Verify source integrity before restoring
    if not verify_backup(source):
        print("[ERROR] Backup integrity check failed — aborting restore.")
        sys.exit(1)

    # Safety copy of current live DB
    if DB_PATH.exists():
        safety = DB_PATH.with_suffix(f".pre_restore_{_timestamp()}.db")
        shutil.copy2(DB_PATH, safety)
        print(f"[INFO] Safety copy saved: {safety.name}")

    shutil.copy2(source, DB_PATH)
    print(f"[OK] Restored {source.name} → {DB_PATH.name}")


def list_backups():
    backups = sorted(BACKUP_DIR.glob(f"{BACKUP_PREFIX}*.db"), reverse=True)
    if not backups:
        print("[INFO] No backups found.")
        return
    print(f"\n{'File':<55} {'Size':>8}")
    print("-" * 65)
    for b in backups:
        size_kb = b.stat().st_size // 1024
        print(f"{b.name:<55} {size_kb:>5} KB")
    print(f"\nTotal: {len(backups)} backup(s) — max retained: {MAX_BACKUPS}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Digital Shadow database backup utility")
    parser.add_argument("--verify", action="store_true", help="Verify backup integrity after creation")
    parser.add_argument("--restore", metavar="FILE", help="Restore from backup file")
    parser.add_argument("--list", action="store_true", help="List available backups")
    args = parser.parse_args()

    if args.list:
        list_backups()
    elif args.restore:
        restore_backup(Path(args.restore))
    else:
        backup = create_backup()
        if backup and args.verify:
            verify_backup(backup)
        if backup:
            rotate_backups()
