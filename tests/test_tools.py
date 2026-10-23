import json
from datetime import date, timedelta

import pytest

from app import models
from app.agent.tools import BidTools


def in_days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.fixture()
def tools(db):
    return BidTools(db)


@pytest.fixture()
def acme(db):
    client = models.Client(name="Acme Corp", industry="Retail", past_bids_won=6, past_bids_lost=2)
    db.add(client)
    db.commit()
    return client


@pytest.fixture()
def bid(db, acme):
    bid = models.Bid(
        client_id=acme.id,
        title="Website redesign",
        value=100000,
        estimated_cost=92000,
        deadline=date.today() + timedelta(days=5),
        status=models.BidStatus.submitted,
        notes="Rush job",
    )
    db.add(bid)
    db.commit()
    return bid


# --- get_bid ---


def test_get_bid_returns_details(tools, bid):
    result = tools.get_bid(bid.id)
    assert result["title"] == "Website redesign"
    assert result["client_name"] == "Acme Corp"
    assert result["value"] == 100000
    assert result["estimated_cost"] == 92000
    assert result["status"] == "submitted"
    assert result["deadline"] == in_days(5)
    assert result["notes"] == "Rush job"


def test_get_bid_missing_returns_clear_message(tools):
    assert tools.get_bid(999) == {"error": "Bid 999 not found"}


# --- get_client_history ---


def test_get_client_history(tools, acme, bid):
    result = tools.get_client_history(acme.id)
    assert result["name"] == "Acme Corp"
    assert result["past_bids_won"] == 6
    assert result["past_bids_lost"] == 2
    assert result["win_rate"] == 0.75
    assert result["bids_on_file"] == 1


def test_client_with_no_history_has_no_win_rate(db, tools):
    newcomer = models.Client(name="Newcomer Ltd")
    db.add(newcomer)
    db.commit()
    assert tools.get_client_history(newcomer.id)["win_rate"] is None


def test_get_client_history_missing_returns_clear_message(tools):
    assert tools.get_client_history(999) == {"error": "Client 999 not found"}


# --- calculate_margin ---


def test_calculate_margin_thin(tools):
    result = tools.calculate_margin(100000, 92000)
    assert result["profit"] == 8000
    assert result["margin_percent"] == 8.0
    assert result["below_threshold"] is True


def test_calculate_margin_healthy():
    result = BidTools.calculate_margin(100000, 60000)  # static: no database needed
    assert result["margin_percent"] == 40.0
    assert result["below_threshold"] is False


def test_calculate_margin_zero_value_returns_error(tools):
    assert "error" in tools.calculate_margin(0, 500)


# --- check_deadline ---


def test_check_deadline_inside_window(tools):
    result = tools.check_deadline(in_days(5))
    assert result["days_left"] == 5
    assert result["is_overdue"] is False
    assert result["within_threshold"] is True


def test_check_deadline_far_away(tools):
    result = tools.check_deadline(in_days(60))
    assert result["days_left"] == 60
    assert result["within_threshold"] is False


def test_check_deadline_overdue(tools):
    result = tools.check_deadline(in_days(-2))
    assert result["days_left"] == -2
    assert result["is_overdue"] is True


def test_check_deadline_bad_date_returns_error(tools):
    assert "error" in tools.check_deadline("next friday")


# --- all results must be plain data the agent can read ---


def test_results_are_json_serialisable(tools, acme, bid):
    for result in (
        tools.get_bid(bid.id),
        tools.get_client_history(acme.id),
        tools.calculate_margin(100000, 92000),
        tools.check_deadline(in_days(5)),
    ):
        json.dumps(result)