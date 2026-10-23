import logging
from collections import Counter
from collections.abc import Iterator

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.agent.agent import assess_bid
from app.exceptions import LLMError, NotFoundError
from app.services.risk import RiskLevel

logger = logging.getLogger(__name__)

# A bid is "open" while we can still act on it
OPEN_STATUSES = (models.BidStatus.draft, models.BidStatus.submitted)


class BidRisk(BaseModel):
    assessment_id: int
    bid_id: int
    title: str
    client_name: str
    score: int
    level: RiskLevel
    baseline_score: int
    reasons: list[str]
    recommendation: str


class FailedBid(BaseModel):
    bid_id: int
    title: str
    error: str


class PortfolioSummary(BaseModel):
    bids_assessed: int
    by_level: dict[str, int]
    top_risks: list[BidRisk]
    failed: list[FailedBid]


def assess_open_bids(db: Session, llm) -> Iterator[BidRisk | FailedBid]:
    """Assess every open bid, one at a time.

    This is a generator: it hands back each result as soon as it is ready instead of
    building one big list first. One bid failing does not stop the others.
    """
    query = select(models.Bid).where(models.Bid.status.in_(OPEN_STATUSES)).order_by(models.Bid.id)
    for bid in db.scalars(query):
        # Read what we need now: assess_bid commits, which refreshes the bid object
        bid_id, title, client_name = bid.id, bid.title, bid.client.name
        try:
            result = assess_bid(db, bid_id, llm=llm)
        except (LLMError, NotFoundError) as exc:
            logger.warning("Skipping bid %s in the summary: %s", bid_id, exc.message)
            yield FailedBid(bid_id=bid_id, title=title, error=exc.message)
            continue
        yield BidRisk(
            assessment_id=result.assessment_id,
            bid_id=bid_id,
            title=title,
            client_name=client_name,
            score=result.report.score,
            level=result.report.level,
            baseline_score=result.baseline.score,
            reasons=result.report.reasons,
            recommendation=result.report.recommendation,
        )


def summarise_portfolio(db: Session, llm, top: int = 5) -> PortfolioSummary:
    """Assess all open bids and report the riskiest ones."""
    assessed: list[BidRisk] = []
    failed: list[FailedBid] = []
    for item in assess_open_bids(db, llm):
        if isinstance(item, FailedBid):
            failed.append(item)
        else:
            assessed.append(item)

    # Highest score first. On a tie, the rule-based score and then the bid id decide,
    # so the order is always the same.
    ranked = sorted(assessed, key=lambda r: (-r.score, -r.baseline_score, r.bid_id))

    counts = Counter(r.level.value for r in assessed)
    by_level = {level.value: counts[level.value] for level in RiskLevel}

    logger.info(
        "Portfolio summary: %s assessed, %s failed, levels %s", len(assessed), len(failed), by_level
    )
    return PortfolioSummary(
        bids_assessed=len(assessed),
        by_level=by_level,
        top_risks=ranked[:top],
        failed=failed,
    )