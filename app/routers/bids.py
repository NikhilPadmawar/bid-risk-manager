from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
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


@router.get("", response_model=list[schemas.BidRead])
def list_bids(
    status_filter: models.BidStatus | None = Query(default=None, alias="status"),
    client_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = select(models.Bid)
    if status_filter is not None:
        query = query.where(models.Bid.status == status_filter)
    if client_id is not None:
        query = query.where(models.Bid.client_id == client_id)
    return db.scalars(query.order_by(models.Bid.id)).all()


@router.get("/{bid_id}", response_model=schemas.BidRead)
def get_bid(bid_id: int, db: Session = Depends(get_db)):
    bid = db.get(models.Bid, bid_id)
    if bid is None:
        raise HTTPException(status_code=404, detail=f"Bid {bid_id} not found")
    return bid