import argparse
from datetime import date

from server.app.services import integrity_service, reconciliation_service
from server.db.database import get_db_session


def _parse_iso_date(raw_value: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {raw_value}. Expected YYYY-MM-DD."
        ) from exc


def _print_blockers(report: dict) -> None:
    if not report["blockers"]:
        print("No blockers.")
        return
    for issue in report["blockers"]:
        print(f"[BLOCKER] {issue['check']} ({issue['count']}) - {issue['message']}")
        for row in issue["rows"][:5]:
            print(f"  sample: {row}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair known integrity blockers (mismatch + postpone chain) and verify strict gate."
    )
    parser.add_argument(
        "--work-date",
        type=_parse_iso_date,
        default=date.today(),
        help="Work date for integrity snapshot verification (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    db = get_db_session()
    try:
        print("Before repair:")
        before_report = integrity_service.run_integrity_report(
            db=db,
            work_date=args.work_date,
            strict=False,
        )
        _print_blockers(before_report)

        repair_summary = reconciliation_service.repair_known_integrity_blockers(db=db)
        print("Repair summary:")
        print(repair_summary)

        print("After repair:")
        after_report = integrity_service.run_integrity_report(
            db=db,
            work_date=args.work_date,
            strict=False,
        )
        _print_blockers(after_report)

        if after_report["blockers"]:
            raise SystemExit(1)

        print("Integrity repair completed successfully. Strict gate is now clear.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
