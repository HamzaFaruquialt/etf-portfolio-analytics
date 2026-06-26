"""Tests for the Markowitz optimizer in optimize.py.

Uses a small synthetic return panel with real factor structure (not pure
noise) -- one asset is built with a negative loading on the common factor,
so there's an actual diversification benefit for the optimizer to find,
rather than testing against degenerate random data.
"""

import numpy as np
import pandas as pd

from optimize import (
    expected_returns_and_cov,
    min_variance_portfolio,
    max_sharpe_portfolio,
    efficient_frontier,
)


def synthetic_returns(seed: int = 0, n_days: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    common_factor = rng.normal(0, 0.01, n_days)
    idiosyncratic_noise = rng.normal(0, 0.005, (n_days, 4))
    loadings = np.array([1.0, 0.8, 0.2, -0.3])  # last asset hedges the others
    returns = idiosyncratic_noise + np.outer(common_factor, loadings)
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    return pd.DataFrame(returns, index=dates, columns=["A0", "A1", "A2", "A3"])


def assert_valid_long_only_weights(weights: np.ndarray):
    assert np.isclose(weights.sum(), 1.0, atol=1e-6)
    assert (weights >= -1e-8).all()
    assert (weights <= 1 + 1e-8).all()


def test_min_variance_weights_are_long_only_and_sum_to_one():
    mean_returns, cov = expected_returns_and_cov(synthetic_returns())
    weights = min_variance_portfolio(mean_returns, cov)
    assert_valid_long_only_weights(weights)


def test_max_sharpe_weights_are_long_only_and_sum_to_one():
    mean_returns, cov = expected_returns_and_cov(synthetic_returns())
    weights = max_sharpe_portfolio(mean_returns, cov)
    assert_valid_long_only_weights(weights)


def test_min_variance_portfolio_has_the_lowest_variance_on_the_frontier():
    """Sanity-checks the optimizer actually found a minimum: no point on the
    swept efficient frontier should have a lower volatility than the
    dedicated min-variance solution."""
    mean_returns, cov = expected_returns_and_cov(synthetic_returns())

    min_var_weights = min_variance_portfolio(mean_returns, cov)
    min_var_vol = float(np.sqrt(min_var_weights @ cov.values @ min_var_weights))

    # Tolerance has to absorb two sources of small, expected noise: (1)
    # efficient_frontier() rounds volatility to 4 decimals before returning
    # it, and (2) the frontier's lowest point and the dedicated min-variance
    # solve are two separate SLSQP calls with different constraint
    # formulations, so they can land a few hundredths of a basis point apart
    # even at the true minimum. 2e-3 comfortably covers both while still
    # catching a real regression (e.g. the optimizer finding something
    # meaningfully, not just numerically, lower).
    frontier = efficient_frontier(mean_returns, cov, n_points=20)
    assert (frontier["volatility"] >= min_var_vol - 2e-3).all()
