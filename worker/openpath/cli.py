"""Operator commands: openpath sources sync | sources list | scan <slug> | scan-all | expire"""

import argparse
import subprocess
import sys
from pathlib import Path

from . import db
from .config import load_settings

SOURCES_FILE = Path(__file__).resolve().parent.parent / "sources.yaml"


def main() -> None:
    parser = argparse.ArgumentParser(prog="openpath")
    commands = parser.add_subparsers(dest="command", required=True)
    sources = commands.add_parser("sources")
    sources.add_argument("action", choices=["sync", "list"])
    scan = commands.add_parser("scan")
    scan.add_argument("slug")
    commands.add_parser("scan-all")
    commands.add_parser("expire")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set. See worker/.env.example.")
    conn = db.connect(settings.database_url)

    if args.command == "sources" and args.action == "sync":
        print(f"Synced {db.sync_sources(conn, SOURCES_FILE)} sources")
    elif args.command == "sources":
        for s in conn.execute("select slug, adapter, enabled, last_status, last_scan_at from sources order by slug"):
            print(f"{s['slug']:<16}{s['adapter']:<14}{'on ' if s['enabled'] else 'off'} {s['last_status'] or 'never scanned':<14}{s['last_scan_at'] or ''}")
    elif args.command == "scan":
        sys.exit(subprocess.run([sys.executable, "-m", "openpath.scan", args.slug]).returncode)
    elif args.command == "scan-all":
        slugs = [s["slug"] for s in conn.execute("select slug from sources where enabled order by slug")]
        for slug in slugs:
            subprocess.run([sys.executable, "-m", "openpath.scan", slug])
    elif args.command == "expire":
        print(f"Expired {db.expire_past_deadlines(conn)} opportunities")


if __name__ == "__main__":
    main()
