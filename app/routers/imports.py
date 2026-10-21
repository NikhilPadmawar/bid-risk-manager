from pathlib import Path

from app.decorators import handle_db_errors

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.csv_import import ImportResult, import_bids

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/bids", response_model=ImportResult)
@handle_db_errors
def import_bids_from_csv(db: Session = Depends(get_db)):
    return import_bids(db, Path(settings.bids_csv_path))