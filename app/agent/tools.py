from datetime import date

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services.risk import RiskScorer


class BidTools:
    """Small lookup functions for the risk agent.

    Each tool returns a plain dictionary. A problem (like a missing bid) comes back as
    {"error": "..."} instead of an exception, so the agent can read it and carry on.

    The docstrings matter: later the AI model reads them to decide which tool to call.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_bid(self, bid_id: int) -> dict:
        """Get the details of one bid by its id: title, client, value, estimated cost,
        deadline (YYYY-MM-DD), status and notes."""
        bid = self.db.get(models.Bid, bid_id)
        if bid is None:
            return {"error": f"Bid {bid_id} not found"}
        return {
            "id": bid.id,
            "title": bid.title,
            "client_id": bid.client_id,
            "client_name": bid.client.name,
            "value": bid.value,
            "estimated_cost": bid.estimated_cost,
            "deadline": bid.deadline.isoformat(),
            "status": bid.status.value,
            "notes": bid.notes,
        }

    def get_client_history(self, client_id: int) -> dict:
        """Get a client's track record with us: how many bids they won and lost,
        their win rate (0 to 1), and how many bids we have on file for them."""
        client = self.db.get(models.Client, client_id)
        if client is None:
            return {"error": f"Client {client_id} not found"}
        total = client.past_bids_won + client.past_bids_lost
        return {
            "client_id": client.id,
            "name": client.name,
            "industry": client.industry,
            "past_bids_won": client.past_bids_won,
            "past_bids_lost": client.past_bids_lost,
            "win_rate": round(client.past_bids_won / total, 2) if total else None,
            "bids_on_file": len(client.bids),
        }

    @staticmethod
    def calculate_margin(value: float, estimated_cost: float) -> dict:
        """Work out the profit and profit margin of a bid from its value and estimated
        cost, and say whether the margin is below our risk threshold."""
        try:
            ratio = RiskScorer.margin_ratio(value, estimated_cost)
        except ValueError as exc:
            return {"error": str(exc)}
        return {
            "profit": value - estimated_cost,
            "margin_percent": round(ratio * 100, 1),
            "threshold_percent": round(settings.risk_margin_threshold * 100, 1),
            "below_threshold": ratio < settings.risk_margin_threshold,
        }

    @staticmethod
    def check_deadline(deadline: str) -> dict:
        """Check how many days are left until a bid deadline (given as YYYY-MM-DD),
        and say whether it is overdue or inside our risk window."""
        try:
            parsed = date.fromisoformat(deadline)
        except ValueError:
            return {"error": f"'{deadline}' is not a valid date, use YYYY-MM-DD"}
        days_left = RiskScorer.days_until(parsed, date.today())
        return {
            "deadline": parsed.isoformat(),
            "days_left": days_left,
            "is_overdue": days_left < 0,
            "threshold_days": settings.risk_deadline_days,
            "within_threshold": days_left < settings.risk_deadline_days,
        }