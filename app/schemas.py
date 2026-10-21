from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    @field_validator("title", "value", "estimated_cost", "deadline", "status")
    @classmethod
    def reject_null(cls, v):
        if v is None:
            raise ValueError("cannot be null")
        return v


class BidRead(BidCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int