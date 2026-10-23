import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BidStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    won = "won"
    lost = "lost"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    industry: Mapped[str | None] = mapped_column(String(100))
    past_bids_won: Mapped[int] = mapped_column(default=0)
    past_bids_lost: Mapped[int] = mapped_column(default=0)

    bids: Mapped[list["Bid"]] = relationship(back_populates="client")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    title: Mapped[str] = mapped_column(String(200))
    value: Mapped[float]
    estimated_cost: Mapped[float]
    deadline: Mapped[date]
    status: Mapped[BidStatus] = mapped_column(Enum(BidStatus), default=BidStatus.draft)
    notes: Mapped[str | None] = mapped_column(Text)

    client: Mapped["Client"] = relationship(back_populates="bids")
    # Deleting a bid also deletes its assessment history
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan"
    )


class Assessment(Base):
    """One saved risk assessment of a bid."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"))
    score: Mapped[int]  # the agent's score
    level: Mapped[str] = mapped_column(String(10))
    reasons: Mapped[list[str]] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(Text)
    baseline_score: Mapped[int]  # the rule-based score at that moment
    baseline_level: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    bid: Mapped["Bid"] = relationship(back_populates="assessments")