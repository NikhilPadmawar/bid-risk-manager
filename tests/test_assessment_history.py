from fakes import BrokenChatModel, ScriptedChatModel, report_call

from app import models
from app.agent.llm import get_llm
from app.main import app


def use_model(model):
    """Make the app use this pretend model instead of the real one."""
    app.dependency_overrides[get_llm] = lambda: model


def assess(client, bid_id, score, level):
    """Run one assessment with a pretend model that reports this score."""
    use_model(ScriptedChatModel(messages=iter([report_call(score, level)])))
    response = client.post(f"/bids/{bid_id}/assess")
    assert response.status_code == 200
    return response.json()


def test_an_assessment_is_saved_and_can_be_read_back(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    result = assess(client, bid["id"], 40, "medium")

    history = client.get(f"/bids/{bid['id']}/assessments")

    assert history.status_code == 200
    [saved] = history.json()
    assert saved["id"] == result["assessment_id"]
    assert saved["bid_id"] == bid["id"]
    assert saved["score"] == 40
    assert saved["level"] == "medium"
    assert saved["reasons"] == result["report"]["reasons"]
    assert saved["recommendation"] == result["report"]["recommendation"]
    assert saved["baseline_score"] == result["baseline"]["score"]
    assert saved["created_at"]


def test_history_lists_the_newest_assessment_first(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    assess(client, bid["id"], 40, "medium")
    assess(client, bid["id"], 57, "high")

    scores = [a["score"] for a in client.get(f"/bids/{bid['id']}/assessments").json()]

    assert scores == [57, 40]


def test_history_only_shows_the_assessments_of_that_bid(client, make_client, make_bid):
    acme = make_client()
    first = make_bid(acme["id"], title="First")
    second = make_bid(acme["id"], title="Second")
    assess(client, first["id"], 40, "medium")
    assess(client, second["id"], 57, "high")

    scores = [a["score"] for a in client.get(f"/bids/{first['id']}/assessments").json()]

    assert scores == [40]


def test_history_is_empty_for_a_bid_never_assessed(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    response = client.get(f"/bids/{bid['id']}/assessments")
    assert response.status_code == 200
    assert response.json() == []


def test_history_for_an_unknown_bid_returns_404(client):
    response = client.get("/bids/999/assessments")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_a_failed_assessment_saves_nothing(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    use_model(BrokenChatModel(messages=iter([])))
    assert client.post(f"/bids/{bid['id']}/assess").status_code == 502

    assert client.get(f"/bids/{bid['id']}/assessments").json() == []


def test_deleting_a_bid_deletes_its_history(client, db, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    assess(client, bid["id"], 40, "medium")
    assert db.query(models.Assessment).count() == 1

    assert client.delete(f"/bids/{bid['id']}").status_code == 204

    db.expire_all()
    assert db.query(models.Assessment).count() == 0