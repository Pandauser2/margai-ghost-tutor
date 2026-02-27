#!/usr/bin/env python3
"""
Delete query_logs older than 30 days. Manual run when you want to prune.
Usage: python scripts/cleanup_logs.py [--dry-run]
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supabase import create_client
from lib.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete query_logs older than 30 days")
    parser.add_argument("--dry-run", action="store_true", help="Only print how many rows would be deleted")
    args = parser.parse_args()

    settings = get_settings()
    url = os.environ.get("SUPABASE_URL") or settings.supabase_url
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or settings.supabase_service_role_key
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        sys.exit(1)

    sb = create_client(url, key)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    r = sb.table("query_logs").select("id").lt("timestamp", cutoff).execute()
    count = len(r.data or [])

    if args.dry_run:
        print(f"Would delete {count} rows with timestamp < {cutoff}")
        return
    if count == 0:
        print("No rows to delete.")
        return
    sb.table("query_logs").delete().lt("timestamp", cutoff).execute()
    print(f"Deleted {count} rows older than 30 days.")


if __name__ == "__main__":
    main()
