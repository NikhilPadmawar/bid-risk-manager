import enum
from datetime import date

from pydantic import BaseModel

from app.config import settings


class RiskLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskResult(BaseModel):
    score: int  # 0 (safe) to 100 (very risky)
    level: RiskLevel
    reasons: list[str]


# Squeezes any number into the range 0.0 to 1.0
clamp = lambda x: max(0.0, min(1.0, x))  # noqa: E731


class RiskScorer:
    """Rule-based risk score. Plain Python: no database and no AI.

    Three signals add up to at most 100 points:
      margin       up to 40 points  (the thinner the margin, the more points)
      deadline     up to 30 points  (the closer or more overdue, the more points)
      client lost  up to 30 points  (the more bids the client lost us, the more points)
    """

    MARGIN_POINTS = 40
    DEADLINE_POINTS = 30
    HISTORY_POINTS = 30

    MEDIUM_FROM = 25  # score 25 to 49 is medium
    HIGH_FROM = 50  # score 50 and above is high

    def __init__(
        self,
        margin_threshold: float = settings.risk_margin_threshold,
        deadline_days: int = settings.risk_deadline_days,
        lost_bids: int = settings.risk_lost_bids,
    ):
        self.margin_threshold = margin_threshold
        self.deadline_days = deadline_days
        self.lost_bids = lost_bids

    @staticmethod
    def margin_ratio(value: float, estimated_cost: float) -> float:
        """Share of the bid value left after costs. 0.08 means an 8% margin."""
        if value <= 0:
            raise ValueError("value must be greater than 0")
        return (value - estimated_cost) / value

    @staticmethod
    def days_until(deadline: date, today: date) -> int:
        """Whole days from today to the deadline. Negative if it has passed."""
        return (deadline - today).days

    @staticmethod
    def level_for(score: int) -> RiskLevel:
        if score >= RiskScorer.HIGH_FROM:
            return RiskLevel.high
        if score >= RiskScorer.MEDIUM_FROM:
            return RiskLevel.medium
        return RiskLevel.low

    def score(
        self,
        value: float,
        estimated_cost: float,
        deadline: date,
        past_bids_lost: int,
        today: date | None = None,
    ) -> RiskResult:
        today = today or date.today()
        margin = self.margin_ratio(value, estimated_cost)
        days_left = self.days_until(deadline, today)

        # Each signal: 0 points when safe, full points when at its worst
        margin_points = self.MARGIN_POINTS * clamp(1 - margin / self.margin_threshold)
        deadline_points = self.DEADLINE_POINTS * clamp(1 - days_left / self.deadline_days)
        history_points = self.HISTORY_POINTS * clamp(past_bids_lost / self.lost_bids)

        reasons = []
        if margin_points > 0:
            reasons.append(
                f"Margin is {margin:.0%}, below the {self.margin_threshold:.0%} threshold"
            )
        if deadline_points > 0:
            if days_left < 0:
                reasons.append(f"Deadline passed {-days_left} day(s) ago")
            else:
                reasons.append(
                    f"Deadline is in {days_left} day(s), within the {self.deadline_days}-day threshold"
                )
        if history_points > 0:
            reasons.append(
                f"Client has {past_bids_lost} lost bid(s), threshold is {self.lost_bids}"
            )

        total = round(margin_points + deadline_points + history_points)
        return RiskResult(score=total, level=self.level_for(total), reasons=reasons)