from datetime import date, timedelta

import pytest

from app.services.risk import RiskLevel, RiskScorer

TODAY = date(2026, 10, 23)
scorer = RiskScorer(margin_threshold=0.15, deadline_days=7, lost_bids=2)


def in_days(n: int) -> date:
    return TODAY + timedelta(days=n)


def test_safe_bid_scores_zero_and_is_low():
    result = scorer.score(
        value=100000, estimated_cost=60000, deadline=in_days(60), past_bids_lost=0, today=TODAY
    )
    assert result.score == 0
    assert result.level == RiskLevel.low
    assert result.reasons == []


def test_worst_case_bid_scores_100_and_is_high():
    result = scorer.score(
        value=100000, estimated_cost=120000, deadline=in_days(-3), past_bids_lost=5, today=TODAY
    )
    assert result.score == 100
    assert result.level == RiskLevel.high
    assert len(result.reasons) == 3


def test_all_three_signals_together_is_high():
    # 8% margin, due in 5 days, client lost us 3 bids
    result = scorer.score(
        value=100000, estimated_cost=92000, deadline=in_days(5), past_bids_lost=3, today=TODAY
    )
    assert result.score == 57
    assert result.level == RiskLevel.high
    assert len(result.reasons) == 3


def test_zero_margin_alone_is_medium():
    result = scorer.score(
        value=100000, estimated_cost=100000, deadline=in_days(60), past_bids_lost=0, today=TODAY
    )
    assert result.score == 40
    assert result.level == RiskLevel.medium
    assert result.reasons == ["Margin is 0%, below the 15% threshold"]


def test_one_lost_bid_is_a_partial_risk():
    result = scorer.score(
        value=100000, estimated_cost=60000, deadline=in_days(60), past_bids_lost=1, today=TODAY
    )
    assert result.score == 15
    assert result.level == RiskLevel.low


def test_deadline_exactly_at_threshold_adds_nothing():
    result = scorer.score(
        value=100000, estimated_cost=60000, deadline=in_days(7), past_bids_lost=0, today=TODAY
    )
    assert result.score == 0


def test_thresholds_can_be_changed():
    strict = RiskScorer(margin_threshold=0.5, deadline_days=30, lost_bids=1)
    result = strict.score(
        value=100000, estimated_cost=80000, deadline=in_days(60), past_bids_lost=0, today=TODAY
    )
    assert result.score == 24  # 20% margin against a 50% threshold: 40 * 0.6


def test_value_of_zero_is_rejected():
    with pytest.raises(ValueError):
        scorer.score(value=0, estimated_cost=10, deadline=in_days(30), past_bids_lost=0, today=TODAY)


@pytest.mark.parametrize(
    "score, level",
    [
        (0, RiskLevel.low),
        (24, RiskLevel.low),
        (25, RiskLevel.medium),
        (49, RiskLevel.medium),
        (50, RiskLevel.high),
        (100, RiskLevel.high),
    ],
)
def test_level_boundaries(score, level):
    assert RiskScorer.level_for(score) == level