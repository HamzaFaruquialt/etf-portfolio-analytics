"""Tests for transform.py's return/cumulative-return math.

Uses a tiny 4-day synthetic price series instead of real ETF data, so the
expected daily/cumulative returns can be traced by hand: 100 -> 105 -> 100
-> 110 is +5%, -4.7619%, +10%.
"""

import math

import pandas as pd

from transform import add_returns


def make_prices(prices: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({
        "ticker": ["TST"] * len(prices),
        "date": dates,
        "adj_close": prices,
        "volume": [1_000] * len(prices),
    })


def test_first_day_has_no_return():
    # There's nothing to compare the first price against, so the first row's
    # return must be NaN, not zero -- zero would silently understate risk.
    out = add_returns(make_prices([100.0, 105.0, 100.0, 110.0]))
    assert math.isnan(out["daily_return"].iloc[0])


def test_daily_return_matches_hand_calculation():
    out = add_returns(make_prices([100.0, 105.0, 100.0, 110.0]))
    expected = [0.05, -1 / 21, 0.10]
    actual = out["daily_return"].iloc[1:].tolist()
    for a, e in zip(actual, expected):
        assert math.isclose(a, e, rel_tol=1e-9)


def test_cumulative_return_compounds_day_over_day():
    # Growth of $1: 1.05 -> 1.05*0.952381=1.00 -> 1.00*1.10=1.10
    out = add_returns(make_prices([100.0, 105.0, 100.0, 110.0]))
    expected = [1.05, 1.00, 1.10]
    actual = out["cumulative_return"].iloc[1:].tolist()
    for a, e in zip(actual, expected):
        assert math.isclose(a, e, rel_tol=1e-6)


def test_rolling_vol_is_nan_with_fewer_rows_than_the_window():
    # The configured rolling window is 21 trading days; with only 4 rows
    # there isn't enough history yet, so every value should be NaN rather
    # than some spuriously small number from a too-short sample.
    out = add_returns(make_prices([100.0, 105.0, 100.0, 110.0]))
    vol_col = next(c for c in out.columns if c.startswith("rolling_vol_"))
    assert out[vol_col].isna().all()
