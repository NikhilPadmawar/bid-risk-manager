from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=schemas.ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(payload: schemas.ClientCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.Client).where(models.Client.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="A client with this name already exists")

    client = models.Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client