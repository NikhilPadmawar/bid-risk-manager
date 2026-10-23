import logging

from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.agent.llm import get_llm
from app.agent.tools import BidTools
from app.config import settings
from app.exceptions import LLMError, NotFoundError

logger = logging.getLogger(__name__)

# Safety limit: stops a confused agent from looping (and spending money)
MAX_STEPS = 12


class AssessmentResult(BaseModel):
    bid_id: int
    assessment: str
    tools_used: list[str]


def build_system_prompt() -> str:
    return f"""You are a bid risk analyst. You assess how risky it is for our company to pursue a client bid.

Always look facts up with your tools. Never guess numbers. Work like this:
1. Call get_bid to read the bid.
2. Call get_client_history for the bid's client.
3. Call calculate_margin with the bid's value and estimated cost.
4. Call check_deadline with the bid's deadline.

Our risk rules: a margin below {settings.risk_margin_threshold:.0%} is risky, a deadline within \
{settings.risk_deadline_days} days (or already passed) is risky, and a client with \
{settings.risk_lost_bids} or more lost bids is risky. The more of these signals, the higher the risk.

Then write a short assessment with:
- the risk level (low, medium or high)
- the reasons, quoting the actual numbers from the tools
- a one-sentence recommendation

If a tool returns an error, say so plainly instead of guessing."""


def build_tools(db: Session) -> list[StructuredTool]:
    """Wrap our plain BidTools methods so the agent can call them.

    The name, description and parameters of each tool come from the function's
    name, docstring and type hints.
    """
    bid_tools = BidTools(db)
    return [
        StructuredTool.from_function(bid_tools.get_bid),
        StructuredTool.from_function(bid_tools.get_client_history),
        StructuredTool.from_function(bid_tools.calculate_margin),
        StructuredTool.from_function(bid_tools.check_deadline),
    ]


def assess_bid(db: Session, bid_id: int, llm=None) -> AssessmentResult:
    """Ask the agent to assess one bid. Pass `llm` in tests to avoid a real model."""
    # Cheap check first, so a missing bid never costs an LLM call
    if db.get(models.Bid, bid_id) is None:
        raise NotFoundError(f"Bid {bid_id} not found")

    agent = create_agent(
        model=llm or get_llm(),
        tools=build_tools(db),
        system_prompt=build_system_prompt(),
    )
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Assess bid {bid_id}."}]},
            config={"recursion_limit": MAX_STEPS},
        )
    except Exception as exc:
        logger.error("Agent failed for bid %s: %s", bid_id, type(exc).__name__, exc_info=True)
        raise LLMError(f"The assessment could not be completed ({type(exc).__name__})") from exc

    messages = result["messages"]
    tools_used = [m.name for m in messages if m.type == "tool"]
    logger.info("Assessed bid %s using tools: %s", bid_id, ", ".join(tools_used))
    return AssessmentResult(bid_id=bid_id, assessment=messages[-1].text, tools_used=tools_used)