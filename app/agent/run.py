"""Assess one bid from the command line.

Run it with:  uv run python -m app.agent.run 6
"""

import sys

from app.agent.agent import assess_bid
from app.database import SessionLocal
from app.exceptions import AppError


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise SystemExit("Usage: uv run python -m app.agent.run <bid_id>")

    with SessionLocal() as db:
        try:
            result = assess_bid(db, int(sys.argv[1]))
        except AppError as exc:
            raise SystemExit(f"{exc.error}: {exc.message}")

    report = result.report
    print(f"Tools used: {', '.join(result.tools_used)}\n")
    print(f"Agent:    {report.score} ({report.level.value})")
    print(f"Baseline: {result.baseline.score} ({result.baseline.level.value})\n")
    print("Reasons:")
    for reason in report.reasons:
        print(f"  - {reason}")
    print(f"\nRecommendation: {report.recommendation}")


if __name__ == "__main__":
    main()