from pathlib import Path

from fakes import ScriptedChatModel, report_call

from app.agent.llm import get_llm
from app.config import settings
from app.main import app

SAMPLE_CSV = Path(__file__).parent.parent / "data" / "bids.csv"


def test_import_the_sample_data_then_summarise_the_portfolio(client, monkeypatch):
    monkeypatch.setattr(settings, "bids_csv_path", str(SAMPLE_CSV))

    imported = client.post("/import/bids").json()
    assert imported == {"created": 16, "duplicates": 0, "errors": []}

    # 16 bids, of which one is won and one is lost, so 14 are open.
    # The pretend model scores them 10, 15, 20 ... 75, in bid order.
    scores = list(range(10, 80, 5))
    assert len(scores) == 14
    levels = ["low" if s < 25 else "medium" if s < 50 else "high" for s in scores]
    replies = [report_call(s, lvl) for s, lvl in zip(scores, levels)]
    app.dependency_overrides[get_llm] = lambda: ScriptedChatModel(messages=iter(replies))

    summary = client.get("/risks/summary?top=3").json()

    assert summary["bids_assessed"] == 14
    assert summary["failed"] == []
    assert [r["score"] for r in summary["top_risks"]] == [75, 70, 65]
    assert sum(summary["by_level"].values()) == 14

    # Every assessed bid now has one entry in its history
    top_bid = summary["top_risks"][0]["bid_id"]
    history = client.get(f"/bids/{top_bid}/assessments").json()
    assert [a["score"] for a in history] == [75]