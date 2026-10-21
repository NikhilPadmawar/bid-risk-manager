from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.decorators import handle_db_errors
from app.exceptions import ConflictError

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=schemas.ClientRead, status_code=status.HTTP_201_CREATED)
@handle_db_errors
def create_client(payload: schemas.ClientCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.Client).where(models.Client.name == payload.name))
    if existing:
        raise ConflictError("A client with this name already exists")

    client = models.Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client