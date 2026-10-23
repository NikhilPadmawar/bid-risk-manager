import pytest
from pydantic import ValidationError

from app.agent.schemas import RiskReport

VALID = {
    "score": 57,
    "level": "high",
    "reasons": ["Margin is 8%"],
    "recommendation": "Raise the price.",
}


def test_valid_report_is_accepted():
    report = RiskReport(**VALID)
    assert report.score == 57
    assert report.level == "high"


@pytest.mark.parametrize("score", [-1, 101])
def test_score_must_be_between_0_and_100(score):
    with pytest.raises(ValidationError):
        RiskReport(**{**VALID, "score": score})


def test_level_must_match_the_score():
    with pytest.raises(ValidationError) as error:
        RiskReport(**{**VALID, "level": "low"})
    assert "does not match score 57" in str(error.value)


def test_level_must_be_a_known_level():
    with pytest.raises(ValidationError):
        RiskReport(**{**VALID, "level": "extreme"})


def test_at_least_one_reason_is_required():
    with pytest.raises(ValidationError):
        RiskReport(**{**VALID, "reasons": []})


def test_recommendation_cannot_be_empty():
    with pytest.raises(ValidationError):
        RiskReport(**{**VALID, "recommendation": ""})