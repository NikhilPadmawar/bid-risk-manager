import logging

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.tools import StructuredTool
from sqlalchemy.orm import Session

from app import models
from app.agent.callbacks import StepLogger
from app.agent.llm import get_llm
from app.agent.schemas import AssessmentResult, RiskReport
from app.agent.tools import BidTools
from app.config import settings
from app.decorators import log_tool_call
from app.exceptions import LLMError, NotFoundError
from app.services.risk import RiskScorer

logger = logging.getLogger(__name__)

# Safety limit: stops a confused agent from looping (and spending money)
MAX_STEPS = 20


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

How to score (0 to 100): margin counts for up to 40 points, the deadline for up to 30 points and \
the client's lost bids for up to 30 points. The thinner the margin, the closer the deadline and the \
more lost bids, the more points. Level must match the score: 0-24 is low, 25-49 is medium, \
50-100 is high.

When you have the facts, submit your final report with a score, a level, reasons that quote the \
actual numbers from the tools, and a one-sentence recommendation. If a tool returns an error, say \
so in the reasons instead of guessing."""


def build_tools(db: Session) -> list[StructuredTool]:
    """Wrap our plain BidTools methods so the agent can call them.

    The name, description and parameters of each tool come from the function's
    name, docstring and type hints.
    """
    bid_tools = BidTools(db)
    return [
          StructuredTool.from_function(log_tool_call(bid_tools.get_bid)),
          StructuredTool.from_function(log_tool_call(bid_tools.get_client_history)),
          StructuredTool.from_function(log_tool_call(bid_tools.calculate_margin)),
          StructuredTool.from_function(log_tool_call(bid_tools.check_deadline)),
    ]


def assess_bid(db: Session, bid_id: int, llm=None) -> AssessmentResult:
    """Ask the agent to assess one bid. Pass `llm` in tests to avoid a real model."""
    # Cheap check first, so a missing bid never costs an LLM call
    bid = db.get(models.Bid, bid_id)
    if bid is None:
        raise NotFoundError(f"Bid {bid_id} not found")

    # response_format makes the agent finish by submitting a RiskReport. If the report
    # fails validation, the error is sent back to the model so it can correct itself.
    agent = create_agent(
        model=llm or get_llm(),
        tools=build_tools(db),
        system_prompt=build_system_prompt(),
        response_format=ToolStrategy(RiskReport),
    )
    logger.info("Assessing bid %s", bid_id)
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Assess bid {bid_id}."}]},
            config={"recursion_limit": MAX_STEPS, "callbacks": [StepLogger(bid_id)]},
        )
    except Exception as exc:
        logger.error("Agent failed for bid %s: %s", bid_id, type(exc).__name__, exc_info=True)
        raise LLMError(f"The assessment could not be completed ({type(exc).__name__})") from exc

    report = result.get("structured_response")
    if report is None:
        logger.error("Agent finished for bid %s without submitting a report", bid_id)
        raise LLMError("The model did not return a risk report")

    tools_used = [m.name for m in result["messages"] if m.type == "tool" and m.name != "RiskReport"]
    baseline = RiskScorer().score(
        value=bid.value,
        estimated_cost=bid.estimated_cost,
        deadline=bid.deadline,
        past_bids_lost=bid.client.past_bids_lost,
    )
       # Keep a history, so we can see how a bid's risk changes over time
    saved = models.Assessment(
        bid_id=bid_id,
        score=report.score,
        level=report.level.value,
        reasons=report.reasons,
        recommendation=report.recommendation,
        baseline_score=baseline.score,
        baseline_level=baseline.level.value,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    logger.info(
        "Assessed bid %s (saved as #%s): agent says %s (%s), rules say %s (%s); tools: %s",
        bid_id, saved.id, report.score, report.level.value, baseline.score, baseline.level.value,
        ", ".join(tools_used),
    )
    return AssessmentResult(
        assessment_id=saved.id,
        bid_id=bid_id,
        report=report,
        baseline=baseline,
        tools_used=tools_used,
    )
    
    return AssessmentResult(bid_id=bid_id, report=report, baseline=baseline, tools_used=tools_used)