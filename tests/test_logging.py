import logging
from datetime import date, timedelta

import pytest
from fakes import ScriptedChatModel, report_call, tool_call
from pydantic import SecretStr

from app import models
from app.agent.agent import assess_bid
from app.config import settings
from app.decorators import log_tool_call
from app.logger import HideSecrets


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


def test_every_tool_call_is_logged_with_its_arguments_and_result(db, bid, caplog):
    caplog.set_level(logging.INFO)
    model = ScriptedChatModel(
        messages=iter([tool_call("get_bid", {"bid_id": bid.id}, "1"), report_call(57, "high")])
    )

    assess_bid(db, bid.id, llm=model)

    assert f"Tool get_bid called with {{'bid_id': {bid.id}}}" in caplog.text
    assert "Tool get_bid finished in" in caplog.text
    assert "Website redesign" in caplog.text  # a piece of the result


def test_a_tool_that_returns_an_error_is_logged_as_a_warning(db, caplog):
    caplog.set_level(logging.INFO)

    @log_tool_call
    def get_bid(bid_id: int):
        return {"error": f"Bid {bid_id} not found"}

    get_bid(bid_id=5)

    [record] = [r for r in caplog.records if "returned an error" in r.getMessage()]
    assert record.levelname == "WARNING"
    assert "Bid 5 not found" in record.getMessage()


def test_a_crashing_tool_is_logged_and_the_error_still_propagates(caplog):
    @log_tool_call
    def broken():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        broken()

    assert "Tool broken crashed" in caplog.text


def test_the_decorator_keeps_the_function_name_and_docstring():
    @log_tool_call
    def lookup(x: int):
        """Look something up."""

    assert lookup.__name__ == "lookup"
    assert lookup.__doc__ == "Look something up."


def test_each_step_of_the_agent_loop_is_logged(db, bid, caplog):
    caplog.set_level(logging.INFO)
    model = ScriptedChatModel(
        messages=iter([tool_call("get_bid", {"bid_id": bid.id}, "1"), report_call(57, "high")])
    )

    assess_bid(db, bid.id, llm=model)

    assert f"Assessing bid {bid.id}" in caplog.text
    assert "step 1: asking the model" in caplog.text
    assert "step 1: the model wants to call get_bid" in caplog.text
    assert "step 2: the model wants to call RiskReport" in caplog.text


def test_the_api_key_is_hidden_if_it_ever_reaches_a_log_message(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr("sk-or-super-secret"))
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "Calling with key %s", ("sk-or-super-secret",), None
    )

    HideSecrets().filter(record)

    assert "sk-or-super-secret" not in record.getMessage()
    assert "Calling with key ***" == record.getMessage()


def test_the_filter_leaves_messages_alone_when_there_is_no_key():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    HideSecrets().filter(record)
    assert record.getMessage() == "hello world"


def test_a_real_assessment_never_logs_the_api_key(db, bid, caplog, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", SecretStr("sk-or-super-secret"))
    caplog.set_level(logging.DEBUG)
    model = ScriptedChatModel(
        messages=iter([tool_call("get_bid", {"bid_id": bid.id}, "1"), report_call(57, "high")])
    )

    assess_bid(db, bid.id, llm=model)

    assert "sk-or-super-secret" not in caplog.text