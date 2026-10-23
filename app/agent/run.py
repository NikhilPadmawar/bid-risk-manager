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

    print(f"Tools used: {', '.join(result.tools_used)}\n")
    print(result.assessment)


if __name__ == "__main__":
    main()