from pydantic import BaseModel, Field, model_validator

from app.services.risk import RiskLevel, RiskResult, RiskScorer


class RiskReport(BaseModel):
    """The final risk report for one bid. Submit this when you have the facts."""

    score: int = Field(ge=0, le=100, description="Risk score from 0 (safe) to 100 (very risky)")
    level: RiskLevel = Field(description="low for 0-24, medium for 25-49, high for 50-100")
    reasons: list[str] = Field(
        min_length=1, description="Short reasons that quote the actual numbers from the tools"
    )
    recommendation: str = Field(min_length=1, description="One sentence on what to do about this bid")

    @model_validator(mode="after")
    def level_must_match_score(self):
        expected = RiskScorer.level_for(self.score)
        if self.level != expected:
            raise ValueError(
                f"level '{self.level.value}' does not match score {self.score}, "
                f"which should be '{expected.value}'"
            )
        return self


class AssessmentResult(BaseModel):
    bid_id: int
    report: RiskReport  # what the agent concluded
    baseline: RiskResult  # the plain rule-based score, for comparison
    tools_used: list[str]