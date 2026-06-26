"""Tests for the shared Sharpe/Sortino/Calmar/max-drawdown formulas in
metrics.py, checked against independently-computed expected values rather
than just re-running the same formula the production code uses.
"""

import math

import pandas as pd

from config import TRADING_DAYS, RISK_FREE_RATE
from metrics import (
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
)

# Chosen so the worst day (-20% on day 2) is easy to trace by hand, and there
# are two down days so downside deviation (needed for Sortino) is defined.
RETURNS = [0.10, -0.20, 0.10, 0.05, -0.03]


def daily_returns() -> pd.Series:
    return pd.Series(RETURNS)


def test_max_drawdown_matches_a_hand_traced_peak_to_trough():
    # Growth of $1: 1.10 -> 0.88 -> 0.968 -> 1.0164 -> 0.985908
    # The running peak never exceeds day 1's 1.10, so every later day's
    # drawdown is (cum / 1.10) - 1. The worst is day 2: 0.88/1.10 - 1 = -0.20.
    result = max_drawdown(daily_returns())
    assert math.isclose(result, -0.20, abs_tol=1e-9)


def test_annualized_return_compounds_the_average_daily_return():
    mean_daily = sum(RETURNS) / len(RETURNS)
    expected = (1 + mean_daily) ** TRADING_DAYS - 1
    assert math.isclose(annualized_return(daily_returns()), expected, rel_tol=1e-9)


def test_sharpe_ratio_is_excess_return_over_total_volatility():
    ann_return = annualized_return(daily_returns())
    ann_vol = annualized_volatility(daily_returns())
    expected = (ann_return - RISK_FREE_RATE) / ann_vol
    assert math.isclose(sharpe_ratio(daily_returns()), expected, rel_tol=1e-9)


def test_sortino_only_penalizes_the_down_days():
    # Downside days are -0.20 and -0.03. Sample std (ddof=1) of those two:
    # mean=-0.115, deviations=+-0.085, variance=0.01445, std~=0.12021.
    downside = [r for r in RETURNS if r < 0]
    mean_d = sum(downside) / len(downside)
    variance = sum((d - mean_d) ** 2 for d in downside) / (len(downside) - 1)
    downside_dev = math.sqrt(variance) * math.sqrt(TRADING_DAYS)

    ann_return = annualized_return(daily_returns())
    expected = (ann_return - RISK_FREE_RATE) / downside_dev
    assert math.isclose(sortino_ratio(daily_returns()), expected, rel_tol=1e-6)


def test_sortino_is_nan_with_at_most_one_down_day():
    # Sample standard deviation needs at least 2 points -- with only one
    # downside observation, ddof=1 std is NaN (0/0). Sortino should surface
    # that as NaN too rather than silently returning something misleading.
    returns = pd.Series([0.05, 0.03, -0.01, 0.02])
    assert math.isnan(sortino_ratio(returns))


def test_calmar_ratio_divides_return_by_worst_drawdown():
    ann_return = annualized_return(daily_returns())
    mdd = max_drawdown(daily_returns())
    expected = ann_return / abs(mdd)
    assert math.isclose(calmar_ratio(daily_returns()), expected, rel_tol=1e-9)
