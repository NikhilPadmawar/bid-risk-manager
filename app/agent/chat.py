"""Talk to the risk agent in plain English.

Run it with:  uv run python -m app.agent.chat

Unlike the assessment agent, this one is not told what to do. It reads your question,
decides which tools it needs, and answers. It remembers the conversation, so you can
ask follow-up questions.
"""

import logging

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import StructuredTool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.agent.agent import assess_bid
from app.agent.llm import get_llm
from app.agent.tools import BidTools
from app.config import settings
from app.database import SessionLocal
from app.decorators import log_tool_call
from app.exceptions import AppError, LLMError
from app.logger import setup_logging
from app.services.risk import RiskScorer

logger = logging.getLogger(__name__)

# A single answer may need several tool calls, so allow more steps than an assessment
MAX_STEPS = 25

OPEN_STATUSES = (models.BidStatus.draft, models.BidStatus.submitted)


def build_chat_prompt() -> str:
    return f"""You are an assistant that helps a bid manager understand risk in their bids.

Always use your tools to look facts up. Never guess a number, a date, a name or a bid id. \
If a tool returns an error, tell the user what went wrong instead of guessing.

Our risk rules: a margin below {settings.risk_margin_threshold:.0%} is risky, a deadline within \
{settings.risk_deadline_days} days (or already passed) is risky, and a client with \
{settings.risk_lost_bids} or more lost bids is risky. Scores run from 0 to 100: 0-24 is low, \
25-49 is medium, 50-100 is high.

Pick the cheapest tool that answers the question:
- riskiest_open_bids and rule_based_score are instant and free. Use them for quick questions.
- run_full_assessment starts a deeper AI assessment, takes a while, costs money and saves a \
record. Only use it when the user asks you to assess or re-assess a bid.
- You cannot create, change or delete bids. If asked, say you can only read and assess them.

Keep answers short and plain. Mention bid ids so the user can follow up, and say which numbers \
come from the tools."""


class ChatTools(BidTools):
    """Everything the assessment agent can do, plus tools for exploring the whole portfolio."""

    def __init__(self, db: Session, llm):
        super().__init__(db)
        self.llm = llm

    def _score(self, bid: models.Bid) -> dict:
        result = RiskScorer().score(
            value=bid.value,
            estimated_cost=bid.estimated_cost,
            deadline=bid.deadline,
            past_bids_lost=bid.client.past_bids_lost,
        )
        return {
            "bid_id": bid.id,
            "title": bid.title,
            "client_name": bid.client.name,
            "score": result.score,
            "level": result.level.value,
            "reasons": result.reasons,
        }

    def list_bids(self, status: str = "") -> dict:
        """List bids with their id, title, client, value, estimated cost, deadline and status.
        Pass status (draft, submitted, won or lost) to see only those. Leave it empty for all."""
        query = select(models.Bid).order_by(models.Bid.id)
        if status:
            if status not in models.BidStatus.__members__:
                return {"error": f"'{status}' is not a status. Use draft, submitted, won or lost"}
            query = query.where(models.Bid.status == models.BidStatus(status))
        bids = self.db.scalars(query).all()
        return {
            "count": len(bids),
            "bids": [
                {
                    "id": b.id,
                    "title": b.title,
                    "client_name": b.client.name,
                    "value": b.value,
                    "estimated_cost": b.estimated_cost,
                    "deadline": b.deadline.isoformat(),
                    "status": b.status.value,
                }
                for b in bids
            ],
        }

    def rule_based_score(self, bid_id: int) -> dict:
        """Instantly work out the plain rule-based risk score (0 to 100), level and reasons
        for one bid. No AI is involved, so it is free and always gives the same answer."""
        bid = self.db.get(models.Bid, bid_id)
        if bid is None:
            return {"error": f"Bid {bid_id} not found"}
        return self._score(bid)

    def riskiest_open_bids(self, top: int = 5) -> dict:
        """Instantly rank the open bids (draft and submitted) by rule-based risk score and
        return the riskiest ones. top is how many to return, between 1 and 20."""
        top = max(1, min(20, top))
        query = select(models.Bid).where(models.Bid.status.in_(OPEN_STATUSES))
        scored = [self._score(bid) for bid in self.db.scalars(query)]
        scored.sort(key=lambda s: (-s["score"], s["bid_id"]))
        return {"open_bids": len(scored), "riskiest": scored[:top]}

    def get_assessment_history(self, bid_id: int) -> dict:
        """Get the saved AI assessments of a bid, newest first (at most 5): when each was made,
        its score and level, the rule-based score at that time, and the recommendation."""
        if self.db.get(models.Bid, bid_id) is None:
            return {"error": f"Bid {bid_id} not found"}
        query = (
            select(models.Assessment)
            .where(models.Assessment.bid_id == bid_id)
            .order_by(models.Assessment.created_at.desc(), models.Assessment.id.desc())
            .limit(5)
        )
        return {
            "bid_id": bid_id,
            "assessments": [
                {
                    "id": a.id,
                    "created_at": a.created_at.isoformat(),
                    "score": a.score,
                    "level": a.level,
                    "baseline_score": a.baseline_score,
                    "recommendation": a.recommendation,
                }
                for a in self.db.scalars(query)
            ],
        }

    def run_full_assessment(self, bid_id: int) -> dict:
        """Run a deep AI assessment of one bid and save it to the bid's history. This is slow
        and costs money, so only use it when the user asks to assess or re-assess a bid."""
        try:
            result = assess_bid(self.db, bid_id, llm=self.llm)
        except AppError as exc:
            return {"error": exc.message}
        return {
            "assessment_id": result.assessment_id,
            "bid_id": bid_id,
            "score": result.report.score,
            "level": result.report.level.value,
            "reasons": result.report.reasons,
            "recommendation": result.report.recommendation,
            "rule_based_score": result.baseline.score,
        }


def build_chat_tools(db: Session, llm) -> list[StructuredTool]:
    tools = ChatTools(db, llm)
    methods = [
        tools.list_bids,
        tools.get_bid,
        tools.get_client_history,
        tools.rule_based_score,
        tools.riskiest_open_bids,
        tools.get_assessment_history,
        tools.run_full_assessment,
    ]
    return [StructuredTool.from_function(log_tool_call(method)) for method in methods]


def message_text(message) -> str:
    """The text of a model reply. Some models return a list of parts instead of a string."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


class ChatSession:
    """One conversation. It keeps every message so far, which is how it remembers."""

    def __init__(self, db: Session, llm=None):
        llm = llm or get_llm()
        self.agent = create_agent(
            model=llm,
            tools=build_chat_tools(db, llm),
            system_prompt=build_chat_prompt(),
        )
        self.messages: list = []

    def ask(self, question: str, callbacks: list | None = None) -> str:
        history = self.messages
        try:
            result = self.agent.invoke(
                {"messages": [*history, {"role": "user", "content": question}]},
                config={"recursion_limit": MAX_STEPS, "callbacks": callbacks or []},
            )
        except Exception as exc:
            logger.error("Chat failed: %s", type(exc).__name__, exc_info=True)
            raise LLMError(f"The assistant could not answer ({type(exc).__name__})") from exc
        self.messages = result["messages"]
        return message_text(self.messages[-1])

    def reset(self) -> None:
        self.messages = []


class ToolPrinter(BaseCallbackHandler):
    """Prints each tool the agent uses while it works, so you can watch it think."""

    def on_tool_start(self, serialized, input_str, *, inputs=None, **kwargs):
        name = (serialized or {}).get("name", "tool")
        shown = ", ".join(f"{k}={v!r}" for k, v in (inputs or {}).items())
        print(f"  [using {name}({shown})]", flush=True)


def main() -> None:
    setup_logging(console=False)  # the chat owns the terminal; logs go to the file only
    try:
        llm = get_llm()
    except AppError as exc:
        raise SystemExit(f"{exc.error}: {exc.message}")

    print("Bid risk assistant. Ask about your bids in plain English.")
    print('For example: "Which open bids are riskiest?" or "Why is bid 11 risky?"')
    print('Type /reset to start over and "exit" to quit. Details are logged in', settings.log_file)

    with SessionLocal() as db:
        session = ChatSession(db, llm)
        while True:
            try:
                question = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                break
            if question == "/reset":
                session.reset()
                print("Conversation cleared.")
                continue
            try:
                answer = session.ask(question, callbacks=[ToolPrinter()])
            except AppError as exc:
                print(f"Sorry, something went wrong: {exc.message}")
                continue
            print(f"\nassistant> {answer}")


if __name__ == "__main__":
    main()