from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.agent import assess_bid
from app.agent.llm import get_llm
from app.agent.schemas import AssessmentRead, AssessmentResult

from app import models, schemas
from app.database import get_db
from app.decorators import handle_db_errors
from app.exceptions import NotFoundError

router = APIRouter(prefix="/bids", tags=["bids"])


def get_bid_or_404(db: Session, bid_id: int) -> models.Bid:
    bid = db.get(models.Bid, bid_id)
    if bid is None:
        raise NotFoundError(f"Bid {bid_id} not found")
    return bid


@router.post("", response_model=schemas.BidRead, status_code=status.HTTP_201_CREATED)
@handle_db_errors
def create_bid(payload: schemas.BidCreate, db: Session = Depends(get_db)):
    if db.get(models.Client, payload.client_id) is None:
        raise NotFoundError(f"Client {payload.client_id} not found")

    bid = models.Bid(**payload.model_dump())
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return bid


@router.get("", response_model=list[schemas.BidRead])
@handle_db_errors
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
@handle_db_errors
def get_bid(bid_id: int, db: Session = Depends(get_db)):
    return get_bid_or_404(db, bid_id)


@router.put("/{bid_id}", response_model=schemas.BidRead)
@handle_db_errors
def update_bid(bid_id: int, payload: schemas.BidUpdate, db: Session = Depends(get_db)):
    bid = get_bid_or_404(db, bid_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(bid, field, value)

    db.commit()
    db.refresh(bid)
    return bid


@router.delete("/{bid_id}", status_code=status.HTTP_204_NO_CONTENT)
@handle_db_errors
def delete_bid(bid_id: int, db: Session = Depends(get_db)):
    bid = get_bid_or_404(db, bid_id)
    db.delete(bid)
    db.commit()


@router.post("/{bid_id}/assess", response_model=AssessmentResult)
@handle_db_errors
def assess_one_bid(bid_id: int, db: Session = Depends(get_db), llm=Depends(get_llm)):
    return assess_bid(db, bid_id, llm=llm)


@router.get("/{bid_id}/assessments", response_model=list[AssessmentRead])
@handle_db_errors
def list_assessments(bid_id: int, db: Session = Depends(get_db)):
    get_bid_or_404(db, bid_id)
    query = (
        select(models.Assessment)
        .where(models.Assessment.bid_id == bid_id)
        .order_by(models.Assessment.created_at.desc(), models.Assessment.id.desc())
    )
    return db.scalars(query).all()