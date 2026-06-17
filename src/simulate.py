"""
Stage 9 — Monte Carlo Value-at-Risk (VaR) and Conditional VaR (CVaR).

Sharpe and max drawdown describe what *already happened*. VaR/CVaR instead
ask a forward-looking risk question an allocator actually needs answered:
"how much could this portfolio plausibly lose tomorrow?" This stage answers
it for both the naive equal-weight portfolio and the optimized max-Sharpe
portfolio from Stage 8, using two different simulation methods on purpose:

  - Parametric Monte Carlo: assumes daily returns are jointly normal, then
    draws thousands of synthetic days from that normal distribution.
  - Historical bootstrap: resamples actual historical days, so it captures
    whatever fat-tail/crash behavior really happened, with no normality
    assumption at all.

Reporting both side by side is deliberate: if the historical VaR is notably
worse than the parametric one, that's evidence the portfolio's real return
distribution has fatter tails than a normal curve would suggest -- a concrete,
defensible talking point rather than just trusting one model.
"""

import json
import logging

import numpy as np
import pandas as pd

from config import MC_NUM_SIMULATIONS, VAR_CONFIDENCE_LEVELS
from db import get_connection, init_schema, replace_table
from analyze import load_processed, returns_matrix

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SIMULATED_STRATEGIES = ["equal_weight", "max_sharpe"]


def load_portfolio_weights(conn, strategy: str, tickers: list[str]) -> np.ndarray:
    """Read a previously-saved weight vector out of the `portfolio` table.

    Simulating risk for a portfolio that's already been chosen (Stage 4 /
    Stage 8) is a separate concern from choosing it, so this stage doesn't
    re-run the optimizer -- it just reads the weights those stages already
    computed and saved.
    """
    row = conn.execute(
        "SELECT weights_json FROM portfolio WHERE strategy = ?", (strategy,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No saved weights for strategy '{strategy}' -- run analyze.py/optimize.py first")
    weights_dict = json.loads(row[0])
    return np.array([weights_dict[t] for t in tickers])


def parametric_simulation(wide: pd.DataFrame, weights: np.ndarray, num_simulations: int, seed: int = 42) -> np.ndarray:
    """Simulate 1-day portfolio returns from a multivariate normal fit to the
    historical daily mean/covariance -- the textbook "Monte Carlo VaR" method.
    """
    rng = np.random.default_rng(seed)
    mean = wide.mean().values
    cov = wide.cov().values
    simulated_daily_returns = rng.multivariate_normal(mean, cov, size=num_simulations)
    return simulated_daily_returns @ weights


def historical_bootstrap_simulation(wide: pd.DataFrame, weights: np.ndarray, num_simulations: int, seed: int = 42) -> np.ndarray:
    """Simulate 1-day portfolio returns by resampling whole historical days
    with replacement.

    Resampling whole days (not each ticker independently) preserves the real
    cross-sectional correlation between ETFs on any given day -- a crash day
    where everything but gold and bonds fell together stays intact in the
    resample, instead of being averaged away into independent draws.
    """
    rng = np.random.default_rng(seed)
    sampled_days = rng.choice(len(wide), size=num_simulations, replace=True)
    sampled_returns = wide.values[sampled_days]
    return sampled_returns @ weights


def value_at_risk(returns: np.ndarray, confidence: float) -> tuple[float, float]:
    """95%/99% VaR and CVaR from a distribution of simulated daily returns.

    VaR is reported as a positive loss fraction: a 95% VaR of 0.02 means
    "there's a 5% chance of losing more than 2% in a day." CVaR answers the
    follow-up question -- when it IS that bad, how bad on average? -- by
    averaging the losses in exactly that worst tail.
    """
    var = -np.percentile(returns, (1 - confidence) * 100)
    tail_losses = returns[returns <= -var]
    cvar = -tail_losses.mean() if len(tail_losses) > 0 else var
    return float(var), float(cvar)


def main():
    df = load_processed()
    wide = returns_matrix(df)
    tickers = list(wide.columns)

    conn = get_connection()
    init_schema(conn)

    rows = []
    for strategy in SIMULATED_STRATEGIES:
        weights = load_portfolio_weights(conn, strategy, tickers)
        simulations = {
            "parametric_monte_carlo": parametric_simulation(wide, weights, MC_NUM_SIMULATIONS),
            "historical_bootstrap": historical_bootstrap_simulation(wide, weights, MC_NUM_SIMULATIONS),
        }
        for method, sim_returns in simulations.items():
            for confidence in VAR_CONFIDENCE_LEVELS:
                var, cvar = value_at_risk(sim_returns, confidence)
                rows.append({
                    "portfolio": strategy,
                    "method": method,
                    "confidence": confidence,
                    "var": round(var, 4),
                    "cvar": round(cvar, 4),
                })
                logger.info(
                    f"{strategy:12s} | {method:22s} | {confidence:.0%} VaR={var:.4f}  CVaR={cvar:.4f}"
                )

    var_results = pd.DataFrame(rows)
    replace_table(conn, "var_results", var_results)
    conn.close()
    logger.info(f"\nSaved {len(var_results)} rows to 'var_results'")


if __name__ == "__main__":
    main()
