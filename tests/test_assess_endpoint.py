from fakes import BrokenChatModel, ScriptedChatModel, tool_call
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from app.agent.llm import get_llm
from app.config import settings
from app.main import app


def use_model(model):
    """Make the app use this pretend model instead of the real one."""
    app.dependency_overrides[get_llm] = lambda: model


def test_assess_returns_the_agents_assessment(client, make_client, make_bid):
    acme = make_client()
    bid = make_bid(acme["id"])
    use_model(
        ScriptedChatModel(
            messages=iter(
                [
                    tool_call("get_bid", {"bid_id": bid["id"]}, "1"),
                    tool_call("get_client_history", {"client_id": acme["id"]}, "2"),
                    AIMessage(content="MEDIUM risk: thin margin."),
                ]
            )
        )
    )

    response = client.post(f"/bids/{bid['id']}/assess")

    assert response.status_code == 200
    assert response.json() == {
        "bid_id": bid["id"],
        "assessment": "MEDIUM risk: thin margin.",
        "tools_used": ["get_bid", "get_client_history"],
    }


def test_assess_unknown_bid_returns_404(client):
    use_model(ScriptedChatModel(messages=iter([])))  # must never be called
    response = client.post("/bids/999/assess")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_assess_model_failure_returns_502(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    use_model(BrokenChatModel(messages=iter([])))
    response = client.post(f"/bids/{bid['id']}/assess")
    assert response.status_code == 502
    assert response.json()["error"] == "llm_error"


def test_assess_without_api_key_returns_503(client, make_client, make_bid, monkeypatch):
    bid = make_bid(make_client()["id"])
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr(""))
    response = client.post(f"/bids/{bid['id']}/assess")
    assert response.status_code == 503
    assert response.json()["error"] == "llm_not_configured"