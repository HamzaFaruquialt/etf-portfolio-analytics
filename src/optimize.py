"""
Stage 8 — Markowitz portfolio optimization.

The naive equal-weight portfolio from Stage 4 (1/8 in every ETF) is a
reasonable baseline, but it isn't an *optimized* allocation — it doesn't use
any information about how volatile each ETF is or how they move together.
This stage answers the question an allocator actually asks: given the same 8
holdings, what's the best mix?

It finds two portfolios on the Markowitz efficient frontier:
  - the minimum-variance portfolio (the lowest risk achievable with this
    universe, regardless of return)
  - the maximum-Sharpe portfolio (the best return per unit of risk — the
    portfolio a rational, risk-averse investor would actually want to hold)
and sweeps the frontier between them, so the dashboard can plot where the
naive equal-weight portfolio sits relative to what was actually achievable.

Long-only, fully-invested throughout (weights >= 0, sum to 1) — this models a
retail/analyst portfolio, not a hedge fund with shorting or leverage.
"""

import json
import logging

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from config import TRADING_DAYS, RISK_FREE_RATE
from db import get_connection, init_schema, replace_table, upsert_rows
from analyze import load_processed, returns_matrix
from metrics import full_stats

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def expected_returns_and_cov(wide: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """Annualized mean-return vector and covariance matrix from daily returns.

    Mean-variance optimization is built on these *simple* annualized moments
    (mean * trading days, covariance * trading days) — that's the standard
    Markowitz convention, and what scipy needs to solve for weights. This is
    different from the compounded annualization metrics.py uses for reporting
    realized performance; the optimizer's job is just to find the weights,
    and the final reported stats for each chosen portfolio are recomputed with
    metrics.full_stats() on its actual realized daily series so every table in
    the database uses one consistent reporting convention.
    """
    mean_returns = wide.mean() * TRADING_DAYS
    cov = wide.cov() * TRADING_DAYS
    return mean_returns, cov


def portfolio_performance(weights: np.ndarray, mean_returns: pd.Series, cov: pd.DataFrame):
    """Annualized return, volatility, and Sharpe ratio implied by a weight vector."""
    ann_return = float(np.dot(weights, mean_returns))
    ann_vol = float(np.sqrt(weights @ cov.values @ weights))
    sharpe = (ann_return - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else np.nan
    return ann_return, ann_vol, sharpe


def _bounds_and_seed(n: int):
    """Long-only bounds (0-100% per ticker) and an equal-weight starting guess."""
    bounds = tuple((0.0, 1.0) for _ in range(n))
    x0 = np.repeat(1 / n, n)
    return bounds, x0


def min_variance_portfolio(mean_returns: pd.Series, cov: pd.DataFrame) -> np.ndarray:
    """Solve for the long-only weight vector with the lowest possible variance."""
    n = len(mean_returns)
    bounds, x0 = _bounds_and_seed(n)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

    def variance(w):
        return w @ cov.values @ w

    result = minimize(variance, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        raise RuntimeError(f"min-variance optimization failed: {result.message}")
    return result.x


def max_sharpe_portfolio(mean_returns: pd.Series, cov: pd.DataFrame) -> np.ndarray:
    """Solve for the long-only weight vector with the highest Sharpe ratio."""
    n = len(mean_returns)
    bounds, x0 = _bounds_and_seed(n)
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

    def negative_sharpe(w):
        _, _, sharpe = portfolio_performance(w, mean_returns, cov)
        return -sharpe if np.isfinite(sharpe) else 0.0

    result = minimize(negative_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
    if not result.success:
        raise RuntimeError(f"max-Sharpe optimization failed: {result.message}")
    return result.x


def efficient_frontier(mean_returns: pd.Series, cov: pd.DataFrame, n_points: int = 50) -> pd.DataFrame:
    """Sweep target returns from the min-variance portfolio's return up to the
    best single holding's return, solving minimum variance at each point.

    This is what the dashboard plots as the frontier curve, with the
    min-variance and max-Sharpe portfolios highlighted as two special points
    sitting on it.
    """
    n = len(mean_returns)
    bounds, x0 = _bounds_and_seed(n)

    min_var_weights = min_variance_portfolio(mean_returns, cov)
    min_ret = float(np.dot(min_var_weights, mean_returns))
    max_ret = float(mean_returns.max())  # best a single all-in holding could do

    rows = []
    for target in np.linspace(min_ret, max_ret, n_points):
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w, t=target: float(np.dot(w, mean_returns)) - t},
        ]

        def variance(w):
            return w @ cov.values @ w

        result = minimize(variance, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        if not result.success:
            continue  # target return infeasible for a long-only portfolio here; skip it

        ann_return, ann_vol, sharpe = portfolio_performance(result.x, mean_returns, cov)
        rows.append({
            "target_return": round(ann_return, 4),
            "volatility": round(ann_vol, 4),
            "sharpe_ratio": round(sharpe, 3),
            "weights_json": json.dumps(
                {t: round(w, 4) for t, w in zip(mean_returns.index, result.x)}
            ),
        })
    return pd.DataFrame(rows)


def portfolio_row(strategy: str, weights: np.ndarray, wide: pd.DataFrame) -> dict:
    """Build one row for the `portfolio` table: realized daily-return stats
    for a weight vector, reported with the same metrics.full_stats() formulas
    used everywhere else, plus the weights themselves for the dashboard's
    allocation view.
    """
    port_daily = wide.dot(weights)
    weights_dict = dict(zip(wide.columns, np.round(weights, 4).tolist()))
    return {
        "strategy": strategy,
        **full_stats(port_daily),
        "weights_json": json.dumps(weights_dict),
    }


def main():
    df = load_processed()
    wide = returns_matrix(df)
    mean_returns, cov = expected_returns_and_cov(wide)

    logger.info("--- Solving for min-variance and max-Sharpe portfolios ---")
    min_var_weights = min_variance_portfolio(mean_returns, cov)
    max_sharpe_weights = max_sharpe_portfolio(mean_returns, cov)

    min_var_row = portfolio_row("min_variance", min_var_weights, wide)
    max_sharpe_row = portfolio_row("max_sharpe", max_sharpe_weights, wide)

    for row in (min_var_row, max_sharpe_row):
        logger.info("\n%s:", row["strategy"])
        for k, v in row.items():
            if k != "strategy":
                logger.info(f"  {k}: {v}")

    logger.info("\n--- Sweeping the efficient frontier ---")
    frontier = efficient_frontier(mean_returns, cov)
    logger.info(f"Solved {len(frontier)} frontier points")

    conn = get_connection()
    init_schema(conn)
    # portfolio is shared with analyze.py (Stage 4), which already wrote the
    # equal_weight row — upsert so these two new rows don't wipe it out
    upsert_rows(conn, "portfolio", pd.DataFrame([min_var_row, max_sharpe_row]))
    # optimization_frontier is owned entirely by this stage
    replace_table(conn, "optimization_frontier", frontier)
    conn.close()
    logger.info("\nSaved min_variance/max_sharpe rows to 'portfolio' and the "
                "frontier sweep to 'optimization_frontier'")


if __name__ == "__main__":
    main()
