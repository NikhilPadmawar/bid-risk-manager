from datetime import date, timedelta

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app import models
from app.agent.agent import assess_bid, build_system_prompt, build_tools
from app.exceptions import LLMError, NotFoundError


class ScriptedChatModel(GenericFakeChatModel):
    """A pretend AI model that plays back a fixed script of replies."""

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


class BrokenChatModel(ScriptedChatModel):
    def _generate(self, *args, **kwargs):
        raise RuntimeError("the model is down")


@pytest.fixture()
def bid(db):
    client = models.Client(name="Acme Corp", past_bids_won=6, past_bids_lost=2)
    db.add(client)
    db.commit()
    bid = models.Bid(
        client_id=client.id,
        title="Website redesign",
        value=100000,
        estimated_cost=92000,
        deadline=date.today() + timedelta(days=5),
    )
    db.add(bid)
    db.commit()
    return bid


def test_agent_calls_tools_then_writes_assessment(db, bid):
    script = iter(
        [
            tool_call("get_bid", {"bid_id": bid.id}, "1"),
            tool_call("get_client_history", {"client_id": bid.client_id}, "2"),
            tool_call("calculate_margin", {"value": 100000, "estimated_cost": 92000}, "3"),
            tool_call("check_deadline", {"deadline": bid.deadline.isoformat()}, "4"),
            AIMessage(content="HIGH risk: 8% margin and the deadline is in 5 days."),
        ]
    )
    result = assess_bid(db, bid.id, llm=ScriptedChatModel(messages=script))

    assert result.bid_id == bid.id
    assert result.assessment == "HIGH risk: 8% margin and the deadline is in 5 days."
    assert result.tools_used == [
        "get_bid",
        "get_client_history",
        "calculate_margin",
        "check_deadline",
    ]


def test_missing_bid_is_rejected_before_calling_the_model(db):
    # An empty script would fail if the model were ever called
    with pytest.raises(NotFoundError):
        assess_bid(db, 999, llm=ScriptedChatModel(messages=iter([])))


def test_model_failure_becomes_a_clean_llm_error(db, bid):
    with pytest.raises(LLMError) as error:
        assess_bid(db, bid.id, llm=BrokenChatModel(messages=iter([])))
    assert "RuntimeError" in error.value.message


def test_tools_are_described_for_the_model(db):
    tools = {t.name: t for t in build_tools(db)}
    assert set(tools) == {"get_bid", "get_client_history", "calculate_margin", "check_deadline"}
    assert "bid" in tools["get_bid"].description.lower()
    assert set(tools["calculate_margin"].args) == {"value", "estimated_cost"}


def test_system_prompt_contains_the_risk_rules():
    prompt = build_system_prompt()
    assert "15%" in prompt
    assert "7 days" in prompt
    assert "Never guess" in prompt