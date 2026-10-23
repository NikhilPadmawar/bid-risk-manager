from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agent.llm import get_llm
from app.agent.portfolio import PortfolioSummary, summarise_portfolio
from app.database import get_db
from app.decorators import handle_db_errors

router = APIRouter(prefix="/risks", tags=["risks"])


@router.get("/summary", response_model=PortfolioSummary)
@handle_db_errors
def portfolio_summary(
    top: int = Query(default=5, ge=1, le=20, description="How many of the riskiest bids to return"),
    db: Session = Depends(get_db),
    llm=Depends(get_llm),
):
    return summarise_portfolio(db, llm, top=top)