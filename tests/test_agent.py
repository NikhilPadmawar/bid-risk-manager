from datetime import date, timedelta

import pytest
from fakes import BrokenChatModel, ScriptedChatModel, report_call, tool_call
from langchain_core.messages import AIMessage

from app import models
from app.agent.agent import assess_bid, build_system_prompt, build_tools
from app.exceptions import LLMError, NotFoundError


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


def lookups(bid):
    """The four lookups a well-behaved agent makes before reporting."""
    return [
        tool_call("get_bid", {"bid_id": bid.id}, "1"),
        tool_call("get_client_history", {"client_id": bid.client_id}, "2"),
        tool_call("calculate_margin", {"value": 100000, "estimated_cost": 92000}, "3"),
        tool_call("check_deadline", {"deadline": bid.deadline.isoformat()}, "4"),
    ]


def test_agent_calls_tools_then_submits_a_report(db, bid):
    model = ScriptedChatModel(messages=iter([*lookups(bid), report_call(57, "high")]))
    result = assess_bid(db, bid.id, llm=model)

    assert db.query(models.Assessment).count() == 1  # saved to the history
    assert result.bid_id == bid.id
    assert result.report.score == 57
    assert result.report.level == "high"
    assert result.report.recommendation == "Raise the price or decline."
    assert result.tools_used == [
        "get_bid",
        "get_client_history",
        "calculate_margin",
        "check_deadline",
    ]


def test_result_includes_the_rule_based_baseline_for_comparison(db, bid):
    model = ScriptedChatModel(messages=iter([*lookups(bid), report_call(40, "medium")]))
    result = assess_bid(db, bid.id, llm=model)

    assert result.report.score == 40  # what the agent said
    assert result.baseline.score == 57  # what the plain rules say
    assert result.baseline.level == "high"


def test_invalid_report_is_sent_back_and_the_agent_corrects_it(db, bid):
    # First report says "low" for a score of 57, which breaks the rule. The second is fixed.
    model = ScriptedChatModel(
        messages=iter(
            [*lookups(bid), report_call(57, "low", "bad"), report_call(57, "high", "good")]
        )
    )
    result = assess_bid(db, bid.id, llm=model)
    assert result.report.level == "high"


def test_agent_that_keeps_submitting_invalid_reports_is_stopped(db, bid):
    endless = [report_call(57, "low", f"bad{i}") for i in range(60)]
    with pytest.raises(LLMError):
        assess_bid(db, bid.id, llm=ScriptedChatModel(messages=iter([*lookups(bid), *endless])))


def test_agent_that_never_submits_a_report_is_an_error(db, bid):
    model = ScriptedChatModel(messages=iter([*lookups(bid), AIMessage(content="Looks risky!")]))
    with pytest.raises(LLMError) as error:
        assess_bid(db, bid.id, llm=model)
    assert "did not return a risk report" in error.value.message
    assert db.query(models.Assessment).count() == 0  # nothing saved


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
    assert "0-24 is low" in prompt