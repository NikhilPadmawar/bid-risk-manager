from datetime import date, timedelta

import pytest
from fakes import BrokenChatModel, ScriptedChatModel, report_call, tool_call
from langchain_core.messages import AIMessage

from app import models
from app.agent.chat import (
    ChatSession,
    ChatTools,
    ToolPrinter,
    build_chat_prompt,
    build_chat_tools,
)
from app.exceptions import LLMError
from app.services.risk import RiskScorer


def add_bid(db, client, title, value=100000, cost=92000, days=5, status=models.BidStatus.draft):
    bid = models.Bid(
        client_id=client.id,
        title=title,
        value=value,
        estimated_cost=cost,
        deadline=date.today() + timedelta(days=days),
        status=status,
    )
    db.add(bid)
    db.commit()
    return bid


@pytest.fixture()
def acme(db):
    client = models.Client(name="Acme Corp", past_bids_won=6, past_bids_lost=2)
    db.add(client)
    db.commit()
    return client


@pytest.fixture()
def tools(db):
    return ChatTools(db, llm=None)


def test_list_bids_returns_every_bid(db, acme, tools):
    add_bid(db, acme, "One")
    add_bid(db, acme, "Two", status=models.BidStatus.won)

    result = tools.list_bids()

    assert result["count"] == 2
    assert [b["title"] for b in result["bids"]] == ["One", "Two"]
    assert result["bids"][0]["client_name"] == "Acme Corp"


def test_list_bids_can_filter_by_status(db, acme, tools):
    add_bid(db, acme, "One")
    add_bid(db, acme, "Two", status=models.BidStatus.won)

    result = tools.list_bids(status="won")

    assert [b["title"] for b in result["bids"]] == ["Two"]


def test_list_bids_rejects_an_unknown_status(tools):
    assert "not a status" in tools.list_bids(status="pending")["error"]


def test_rule_based_score_matches_the_scorer(db, acme, tools):
    bid = add_bid(db, acme, "One")
    expected = RiskScorer().score(bid.value, bid.estimated_cost, bid.deadline, 2)

    result = tools.rule_based_score(bid.id)

    assert result["score"] == expected.score
    assert result["level"] == expected.level.value
    assert result["reasons"] == expected.reasons


def test_rule_based_score_for_an_unknown_bid_is_an_error_not_a_crash(tools):
    assert tools.rule_based_score(999) == {"error": "Bid 999 not found"}


def test_riskiest_open_bids_ranks_open_bids_only(db, acme, tools):
    safe = add_bid(db, acme, "Safe", value=100000, cost=50000, days=60)
    risky = add_bid(db, acme, "Risky", value=100000, cost=99000, days=2)
    add_bid(db, acme, "Won already", value=100000, cost=99000, days=2, status=models.BidStatus.won)

    result = tools.riskiest_open_bids()

    assert result["open_bids"] == 2
    assert [b["bid_id"] for b in result["riskiest"]] == [risky.id, safe.id]


def test_riskiest_open_bids_respects_top(db, acme, tools):
    for i in range(4):
        add_bid(db, acme, f"Bid {i}", days=3 + i)

    assert len(tools.riskiest_open_bids(top=2)["riskiest"]) == 2
    assert len(tools.riskiest_open_bids(top=0)["riskiest"]) == 1  # clamped to at least 1


def test_assessment_history_is_empty_then_newest_first(db, acme, tools):
    bid = add_bid(db, acme, "One")
    assert tools.get_assessment_history(bid.id)["assessments"] == []

    for score, level in [(40, "medium"), (80, "high")]:
        db.add(
            models.Assessment(
                bid_id=bid.id, score=score, level=level, reasons=["x"],
                recommendation="r", baseline_score=50, baseline_level="high",
            )
        )
        db.commit()

    scores = [a["score"] for a in tools.get_assessment_history(bid.id)["assessments"]]
    assert scores == [80, 40]


def test_assessment_history_for_an_unknown_bid_is_an_error(tools):
    assert "not found" in tools.get_assessment_history(999)["error"]


def test_run_full_assessment_runs_the_assessment_agent_and_saves_it(db, acme):
    bid = add_bid(db, acme, "One")
    model = ScriptedChatModel(messages=iter([report_call(70, "high")]))

    result = ChatTools(db, llm=model).run_full_assessment(bid.id)

    assert result["score"] == 70
    assert result["level"] == "high"
    assert result["rule_based_score"] == 57
    assert db.query(models.Assessment).count() == 1


def test_run_full_assessment_failures_come_back_as_errors(db, acme):
    bid = add_bid(db, acme, "One")
    broken = ChatTools(db, llm=BrokenChatModel(messages=iter([])))

    assert "could not be completed" in broken.run_full_assessment(bid.id)["error"]
    assert broken.run_full_assessment(999)["error"] == "Bid 999 not found"


def test_chat_tools_are_described_for_the_model(db):
    tools = {t.name: t for t in build_chat_tools(db, llm=None)}
    assert set(tools) == {
        "list_bids", "get_bid", "get_client_history", "rule_based_score",
        "riskiest_open_bids", "get_assessment_history", "run_full_assessment",
    }
    assert "status" in tools["list_bids"].args
    assert "costs money" in tools["run_full_assessment"].description


def test_the_prompt_tells_the_model_not_to_guess_and_not_to_change_data():
    prompt = build_chat_prompt()
    assert "Never guess" in prompt
    assert "cannot create, change or delete" in prompt
    assert "15%" in prompt


def test_session_answers_after_using_a_tool(db, acme):
    risky = add_bid(db, acme, "Risky", value=100000, cost=99000, days=2)
    model = ScriptedChatModel(
        messages=iter(
            [
                tool_call("riskiest_open_bids", {"top": 1}, "1"),
                AIMessage(content=f"Bid {risky.id} is the riskiest."),
            ]
        )
    )

    answer = ChatSession(db, llm=model).ask("Which bid is riskiest?")

    assert answer == f"Bid {risky.id} is the riskiest."


def test_session_remembers_earlier_messages(db, acme):
    model = ScriptedChatModel(
        messages=iter([AIMessage(content="First answer."), AIMessage(content="Second answer.")])
    )
    session = ChatSession(db, llm=model)

    session.ask("Hello")
    assert len(session.messages) == 2  # the question and the answer
    session.ask("And now?")
    assert len(session.messages) == 4  # the first exchange is still there
    assert session.messages[0].content == "Hello"


def test_reset_makes_the_session_forget(db, acme):
    model = ScriptedChatModel(messages=iter([AIMessage(content="Hi.")]))
    session = ChatSession(db, llm=model)
    session.ask("Hello")

    session.reset()

    assert session.messages == []


def test_a_model_failure_becomes_a_clean_error_and_keeps_the_history(db, acme):
    session = ChatSession(db, llm=BrokenChatModel(messages=iter([])))
    with pytest.raises(LLMError) as error:
        session.ask("Hello")
    assert "could not answer" in error.value.message
    assert session.messages == []


def test_chat_can_start_a_full_assessment(db, acme):
    bid = add_bid(db, acme, "One")
    model = ScriptedChatModel(
        messages=iter(
            [
                tool_call("run_full_assessment", {"bid_id": bid.id}, "1"),  # the chat asks
                report_call(70, "high"),  # the assessment agent inside answers
                AIMessage(content="Bid 1 scored 70, which is high."),  # the chat replies
            ]
        )
    )

    answer = ChatSession(db, llm=model).ask("Please assess bid 1")

    assert answer == "Bid 1 scored 70, which is high."
    assert db.query(models.Assessment).count() == 1


def test_the_printer_shows_which_tool_is_being_used(db, acme, capsys):
    model = ScriptedChatModel(
        messages=iter(
            [tool_call("list_bids", {"status": "draft"}, "1"), AIMessage(content="None.")]
        )
    )

    ChatSession(db, llm=model).ask("List drafts", callbacks=[ToolPrinter()])

    assert "[using list_bids(status='draft')]" in capsys.readouterr().out