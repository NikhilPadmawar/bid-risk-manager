from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/bids", tags=["bids"])


@router.post("", response_model=schemas.BidRead, status_code=status.HTTP_201_CREATED)
def create_bid(payload: schemas.BidCreate, db: Session = Depends(get_db)):
    client = db.get(models.Client, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {payload.client_id} not found")

    bid = models.Bid(**payload.model_dump())
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return bid