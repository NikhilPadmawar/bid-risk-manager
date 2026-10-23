from datetime import date

import pytest
from fakes import ScriptedChatModel, report_call
from pydantic import SecretStr

from app import models
from app.agent import portfolio
from app.agent.llm import get_llm
from app.agent.portfolio import FailedBid, assess_open_bids
from app.config import settings
from app.exceptions import LLMError
from app.main import app


def use_scores(*scores):
    """A pretend model that gives these scores to the bids, in order."""
    levels = {True: "high", False: "medium"}
    replies = [
        report_call(score, "low" if score < 25 else levels[score >= 50]) for score in scores
    ]
    app.dependency_overrides[get_llm] = lambda: ScriptedChatModel(messages=iter(replies))


def make_bids(make_client, make_bid, count, **overrides):
    acme = make_client()
    return [make_bid(acme["id"], title=f"Bid {i + 1}", **overrides) for i in range(count)]


def test_summary_ranks_the_riskiest_bids_first(client, make_client, make_bid):
    make_bids(make_client, make_bid, 3)
    use_scores(30, 80, 55)

    data = client.get("/risks/summary").json()

    assert data["bids_assessed"] == 3
    assert [r["score"] for r in data["top_risks"]] == [80, 55, 30]
    assert [r["title"] for r in data["top_risks"]] == ["Bid 2", "Bid 3", "Bid 1"]
    assert data["top_risks"][0]["client_name"] == "Acme Corp"
    assert data["top_risks"][0]["reasons"]


def test_summary_only_returns_the_top_five_by_default(client, make_client, make_bid):
    make_bids(make_client, make_bid, 7)
    use_scores(10, 20, 30, 40, 50, 60, 70)

    data = client.get("/risks/summary").json()

    assert data["bids_assessed"] == 7  # all were assessed...
    assert [r["score"] for r in data["top_risks"]] == [70, 60, 50, 40, 30]  # ...5 are shown


def test_top_can_be_changed(client, make_client, make_bid):
    make_bids(make_client, make_bid, 4)
    use_scores(10, 20, 30, 40)

    data = client.get("/risks/summary?top=2").json()

    assert [r["score"] for r in data["top_risks"]] == [40, 30]


@pytest.mark.parametrize("top", [0, 21, "abc"])
def test_top_must_be_a_sensible_number(client, top):
    use_scores()
    assert client.get(f"/risks/summary?top={top}").status_code == 422


def test_summary_counts_bids_per_level(client, make_client, make_bid):
    make_bids(make_client, make_bid, 4)
    use_scores(10, 30, 35, 90)

    data = client.get("/risks/summary").json()

    assert data["by_level"] == {"low": 1, "medium": 2, "high": 1}


def test_only_open_bids_are_assessed(client, make_client, make_bid):
    acme = make_client()
    make_bid(acme["id"], title="Draft", status="draft")
    make_bid(acme["id"], title="Submitted", status="submitted")
    make_bid(acme["id"], title="Won", status="won")
    make_bid(acme["id"], title="Lost", status="lost")
    use_scores(40, 60)  # exactly two replies: a third model call would fail

    data = client.get("/risks/summary").json()

    assert data["bids_assessed"] == 2
    assert data["failed"] == []
    assert {r["title"] for r in data["top_risks"]} == {"Draft", "Submitted"}


def test_no_open_bids_gives_an_empty_summary(client):
    use_scores()
    data = client.get("/risks/summary").json()
    assert data == {
        "bids_assessed": 0,
        "by_level": {"low": 0, "medium": 0, "high": 0},
        "top_risks": [],
        "failed": [],
    }


def test_ties_are_ordered_the_same_way_every_time(client, make_client, make_bid):
    make_bids(make_client, make_bid, 3)
    use_scores(50, 50, 50)

    data = client.get("/risks/summary").json()

    assert [r["title"] for r in data["top_risks"]] == ["Bid 1", "Bid 2", "Bid 3"]


def test_one_failing_bid_does_not_stop_the_others(client, make_client, make_bid, monkeypatch):
    make_bids(make_client, make_bid, 3)
    real_assess = portfolio.assess_bid

    def flaky(db, bid_id, llm=None):
        if bid_id == 2:
            raise LLMError("The model is down")
        return real_assess(db, bid_id, llm=llm)

    monkeypatch.setattr(portfolio, "assess_bid", flaky)
    use_scores(40, 70)

    data = client.get("/risks/summary").json()

    assert data["bids_assessed"] == 2
    assert [r["score"] for r in data["top_risks"]] == [70, 40]
    assert data["failed"] == [{"bid_id": 2, "title": "Bid 2", "error": "The model is down"}]


def test_every_assessment_in_the_summary_is_saved_to_the_history(client, make_client, make_bid):
    bids = make_bids(make_client, make_bid, 2)
    use_scores(40, 70)

    client.get("/risks/summary")

    for bid in bids:
        assert len(client.get(f"/bids/{bid['id']}/assessments").json()) == 1


def test_assess_open_bids_is_lazy_and_does_one_bid_at_a_time(db, monkeypatch):
    client = models.Client(name="Acme")
    db.add(client)
    db.commit()
    for i in range(3):
        db.add(
            models.Bid(
                client_id=client.id, title=f"Bid {i}", value=100, estimated_cost=80,
                deadline=date(2026, 12, 1),
            )
        )
    db.commit()
    calls = []

    def fake_assess(db, bid_id, llm=None):
        calls.append(bid_id)
        raise LLMError("x")

    monkeypatch.setattr(portfolio, "assess_bid", fake_assess)

    results = assess_open_bids(db, llm=None)
    assert calls == []  # creating the generator does no work

    first = next(results)
    assert isinstance(first, FailedBid)
    assert calls == [1]  # only the first bid was touched


def test_summary_without_an_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(""))
    response = client.get("/risks/summary")
    assert response.status_code == 503
    assert response.json()["error"] == "llm_not_configured"