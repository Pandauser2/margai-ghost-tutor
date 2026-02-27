#!/usr/bin/env python3
"""
Weekly insight report: query query_logs (last 7 days, institute_id=1), compute totals, escalation %, top topics.
Output = email body text only; you send the email manually.
Usage: python scripts/weekly_report.py [--institute-id 1]
"""
import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supabase import create_client
from lib.config import get_settings

# Placeholder topic keywords (JEE, NEET, UPSC) for counting
TOPIC_KEYWORDS = {
    "jee": ["kinematics", "thermodynamics", "electrochemistry", "chemical bonding", "mechanics", "algebra"],
    "neet": ["biology", "anatomy", "physiology", "botany", "zoology", "cell"],
    "upsc": ["polity", "history", "geography", "economy", "environment", "governance"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly insight report (email body text)")
    parser.add_argument("--institute-id", type=int, default=1, help="Institute ID (default 1)")
    args = parser.parse_args()

    settings = get_settings()
    url = os.environ.get("SUPABASE_URL") or settings.supabase_url
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or settings.supabase_service_role_key
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        sys.exit(1)

    sb = create_client(url, key)
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    r = sb.table("query_logs").select("id,query_text,escalated,student_telegram_id,student_name").eq("institute_id", args.institute_id).gte("timestamp", since).execute()
    rows = r.data or []

    total = len(rows)
    escalated_count = sum(1 for row in rows if row.get("escalated"))
    escalation_pct = (100.0 * escalated_count / total) if total else 0.0

    # Top topics: count keyword matches in query_text (case-insensitive)
    topic_counts: Counter = Counter()
    for row in rows:
        q = (row.get("query_text") or "").lower()
        for category, keywords in TOPIC_KEYWORDS.items():
            for kw in keywords:
                if kw in q:
                    topic_counts[category] += 1
                    break
    top_topics = topic_counts.most_common(5)

    # Top students by query count
    student_counts: Counter = Counter()
    for row in rows:
        sid = row.get("student_telegram_id") or "unknown"
        student_counts[sid] += 1
    top_students = student_counts.most_common(5)

    # Who escalated (student_telegram_id where escalated=true)
    escalated_students = list({(row.get("student_telegram_id"), row.get("student_name")) for row in rows if row.get("escalated")})

    # Build email body
    inst = sb.table("institutes").select("email_for_report").eq("id", args.institute_id).execute()
    to_email = (inst.data or [{}])[0].get("email_for_report") or ""

    lines = [
        "MargAI Ghost Tutor – Weekly Insight Report",
        "===========================================",
        f"Period: last 7 days (until {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})",
        f"Institute ID: {args.institute_id}",
        "",
        f"Total queries: {total}",
        f"Escalation rate: {escalation_pct:.1f}% ({escalated_count} escalated)",
        "",
        "Top 5 topic categories (by keyword match):",
    ]
    for topic, count in top_topics:
        lines.append(f"  - {topic}: {count}")
    lines.extend([
        "",
        "Top 5 students by query count:",
    ])
    for sid, count in top_students:
        lines.append(f"  - {sid}: {count} queries")
    if escalated_students:
        lines.extend([
            "",
            "Students who had at least one escalation:",
        ])
        for sid, name in escalated_students[:20]:
            lines.append(f"  - {sid} ({name or '—'})")
    lines.extend([
        "",
        "---",
    ])
    if to_email:
        lines.append(f"To: {to_email}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
