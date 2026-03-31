import argparse
from datetime import date

from server.app.services import integrity_service
from server.db.database import get_db_session


def _parse_iso_date(raw_value: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {raw_value}. Expected YYYY-MM-DD."
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run operational integrity snapshot checks for BexLogix MVP."
    )
    parser.add_argument(
        "--work-date",
        type=_parse_iso_date,
        default=date.today(),
        help="Target work date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any blocker is detected.",
    )
    args = parser.parse_args()

    db = get_db_session()
    try:
        report = integrity_service.run_integrity_report(
            db=db,
            work_date=args.work_date,
            strict=args.strict,
        )
    finally:
        db.close()

    print(f"Integrity snapshot for work_date={report['work_date']}")
    print(
        "Summary: blockers={blocker_checks} warnings={warning_checks} "
        "blocker_rows={total_blocker_rows} warning_rows={total_warning_rows}".format(
            **report["summary"]
        )
    )

    for issue in report["blockers"]:
        print(f"[BLOCKER] {issue['check']} ({issue['count']}) - {issue['message']}")
        for row in issue["rows"][:5]:
            print(f"  sample: {row}")

    for issue in report["warnings"]:
        print(f"[WARNING] {issue['check']} ({issue['count']}) - {issue['message']}")
        for row in issue["rows"][:5]:
            print(f"  sample: {row}")

    if args.strict and report["blockers"]:
        raise SystemExit(1)

    print("Integrity snapshot completed.")


if __name__ == "__main__":
    main()
