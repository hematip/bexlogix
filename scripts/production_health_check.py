"""Production health check.

Runs the database integrity report plus a handful of additional sanity
checks that are useful before a manager triggers the daily pipeline.

Usage:
    python scripts/production_health_check.py [--work-date YYYY-MM-DD]
                                               [--strict]
                                               [--json]

Exit code is 0 on a green report, 1 if blockers exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.app.services.integrity_service import run_integrity_report  # noqa: E402
from server.db.create_tables import create_tables  # noqa: E402
from server.db.database import get_db_session  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-date",
        type=lambda raw: date.fromisoformat(raw),
        default=date.today(),
        help="Target work date for date-scoped checks (default: today).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as blockers (exit 1 on any warning).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    return parser.parse_args()


def _print_human_summary(report: dict, strict: bool) -> None:
    summary = report["summary"]
    work_date = report["work_date"]
    print(f"Production health for {work_date}")
    print(f"  blocker_checks : {summary['blocker_checks']}")
    print(f"  warning_checks : {summary['warning_checks']}")
    print(f"  blocker rows   : {summary['total_blocker_rows']}")
    print(f"  warning rows   : {summary['total_warning_rows']}")

    for issue in report["blockers"]:
        print(f"  [BLOCK] {issue['check']}: {issue['message']} (rows={issue['count']})")
    for issue in report["warnings"]:
        print(f"  [WARN ] {issue['check']}: {issue['message']} (rows={issue['count']})")

    if summary["ok"] and (not strict or summary["total_warning_rows"] == 0):
        print("OK")


def main() -> int:
    args = _parse_args()
    # Ensure schema + unique-index migrations are applied before we read.
    create_tables()
    db = get_db_session()
    try:
        report = run_integrity_report(db=db, work_date=args.work_date, strict=args.strict)
    finally:
        db.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_human_summary(report, strict=args.strict)

    has_blockers = report["summary"]["total_blocker_rows"] > 0
    has_warnings = report["summary"]["total_warning_rows"] > 0
    if has_blockers or (args.strict and has_warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
