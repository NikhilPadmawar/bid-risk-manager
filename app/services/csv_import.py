import csv
import logging
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from app.exceptions import ImportFileError

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)


class BidImportRow(BaseModel):
    """One CSV row, validated before anything touches the database."""

    client_name: str = Field(min_length=1, max_length=100)
    industry: str | None = None
    past_bids_won: int = Field(default=0, ge=0)
    past_bids_lost: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=200)
    value: float = Field(gt=0)
    estimated_cost: float = Field(ge=0)
    deadline: date
    status: models.BidStatus = models.BidStatus.draft
    notes: str | None = None


class ImportResult(BaseModel):
    created: int = 0
    duplicates: int = 0
    errors: list[str] = []


def read_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield (line_number, row) one at a time, without loading the whole file."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for line_number, row in enumerate(reader, start=2):  # line 1 is the header
                yield line_number, {k: v.strip() for k, v in row.items() if k and v and v.strip()}
    except FileNotFoundError as exc:
        raise ImportFileError(f"CSV file not found: {path}") from exc
    except (csv.Error, UnicodeDecodeError) as exc:
        raise ImportFileError(f"CSV file could not be read: {exc}") from exc


def import_bids(db: Session, path: Path) -> ImportResult:
    result = ImportResult()

    for line_number, row in read_rows(path):
        try:
            data = BidImportRow(**row)
        except ValidationError as exc:
            first = exc.errors()[0]
            field_name = first["loc"][0] if first["loc"] else "row"
            result.errors.append(f"line {line_number}: {field_name}: {first['msg']}")
            continue

        client = db.scalar(select(models.Client).where(models.Client.name == data.client_name))
        if client is None:
            client = models.Client(
                name=data.client_name,
                industry=data.industry,
                past_bids_won=data.past_bids_won,
                past_bids_lost=data.past_bids_lost,
            )
            db.add(client)
            db.flush()  # gives the new client an id without committing yet

        already_there = db.scalar(
            select(models.Bid).where(
                models.Bid.client_id == client.id, models.Bid.title == data.title
            )
        )
        if already_there:
            result.duplicates += 1
            continue

        db.add(
            models.Bid(
                client_id=client.id,
                title=data.title,
                value=data.value,
                estimated_cost=data.estimated_cost,
                deadline=data.deadline,
                status=data.status,
                notes=data.notes,
            )
        )
        db.flush()
        result.created += 1

    db.commit()
    logger.info(
        "CSV import finished: %d created, %d duplicates, %d errors",
        result.created, result.duplicates, len(result.errors),
    )
    return result