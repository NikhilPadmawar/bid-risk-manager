from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models import BidStatus


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    past_bids_won: int = Field(default=0, ge=0)
    past_bids_lost: int = Field(default=0, ge=0)


class ClientRead(ClientCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class BidCreate(BaseModel):
    client_id: int
    title: str = Field(min_length=1, max_length=200)
    value: float = Field(gt=0)
    estimated_cost: float = Field(ge=0)
    deadline: date
    status: BidStatus = BidStatus.draft
    notes: str | None = None


class BidUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    value: float | None = Field(default=None, gt=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    deadline: date | None = None
    status: BidStatus | None = None
    notes: str | None = None


class BidRead(BidCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int