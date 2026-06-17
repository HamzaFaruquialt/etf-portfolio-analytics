"""
Stage 10 — Walk-forward backtest.

Everything up to Stage 9 answers "looking back at the full 10 years, which
portfolio would have been best?" That's a fair question, but it's not how
real money gets allocated — you never get to see the future return data
you're optimizing on. This stage fixes that: it rebalances annually using
only the trailing lookback window of data available *as of* that rebalance
date, then scores the resulting portfolio against what actually happened
afterward. That's the only honest way to ask "would this strategy have
actually worked," and it's compared against two baselines: a periodically
rebalanced equal-weight portfolio, and just buying SPY and doing nothing.

Lookahead-bias rule, stated precisely: at rebalance date t, the optimizer
only sees daily returns with date < t — specifically the trailing
BACKTEST_LOOKBACK_YEARS years ending the day before t. The resulting weights
are then held fixed and applied to realized returns from t until the next
rebalance date. The optimizer never sees the period it's later scored on.
"""

import logging

import numpy as np
import pandas as pd

from config import BACKTEST_LOOKBACK_YEARS
from db import get_connection, init_schema, replace_table
from analyze import load_processed, returns_matrix
from optimize import expected_returns_and_cov, max_sharpe_portfolio
from metrics import cumulative_growth, full_stats

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def walk_forward_weights(wide: pd.DataFrame) -> dict:
    """Pick a max-Sharpe allocation at each annual rebalance date, using only
    data strictly before that date (see module docstring for the exact rule).

    Skips the first BACKTEST_LOOKBACK_YEARS years of the dataset entirely,
    since there isn't yet enough trailing history to make a decision.
    """
    years_available = sorted(wide.index.year.unique())
    first_rebalance_year = years_available[0] + BACKTEST_LOOKBACK_YEARS
    rebalance_years = [y for y in years_available if y >= first_rebalance_year]

    schedule = {}
    for year in rebalance_years:
        rebalance_date = wide.index[wide.index.year == year].min()
        lookback_start = rebalance_date - pd.DateOffset(years=BACKTEST_LOOKBACK_YEARS)
        window = wide.loc[(wide.index >= lookback_start) & (wide.index < rebalance_date)]

        mean_returns, cov = expected_returns_and_cov(window)
        schedule[rebalance_date] = max_sharpe_portfolio(mean_returns, cov)
    return schedule


def equal_weight_schedule(wide: pd.DataFrame, rebalance_dates: list) -> dict:
    """The equal-weight baseline doesn't need optimizing — it's the same 1/N
    weights at every rebalance date, so drift between rebalances gets reset
    on the identical schedule as the optimized strategy for a fair comparison.
    """
    n = wide.shape[1]
    weights = np.repeat(1 / n, n)
    return {d: weights for d in rebalance_dates}


def apply_weights_over_time(wide: pd.DataFrame, weight_schedule: dict) -> pd.Series:
    """Apply a schedule of rebalance weights to realized daily returns.

    Each trading day uses whichever weight vector was most recently set at
    or before that day; weights don't change again until the next scheduled
    rebalance. The backtest period starts at the first rebalance date, since
    there's no strategy to score before a decision has actually been made.
    """
    rebalance_dates = pd.DatetimeIndex(sorted(weight_schedule.keys()))
    period = wide.loc[wide.index >= rebalance_dates[0]]

    weight_matrix = np.array([weight_schedule[d] for d in rebalance_dates])
    # for each trading day, find the most recent rebalance date at or before it
    idx = np.searchsorted(rebalance_dates.values, period.index.values, side="right") - 1
    applied_weights = weight_matrix[idx]

    daily_returns = (period.values * applied_weights).sum(axis=1)
    return pd.Series(daily_returns, index=period.index)


def main():
    df = load_processed()
    wide = returns_matrix(df)

    logger.info("--- Building walk-forward max-Sharpe rebalance schedule ---")
    optimized_schedule = walk_forward_weights(wide)
    rebalance_dates = sorted(optimized_schedule.keys())
    logger.info(f"Rebalance dates: {[d.date().isoformat() for d in rebalance_dates]}")

    equal_schedule = equal_weight_schedule(wide, rebalance_dates)

    optimized_daily = apply_weights_over_time(wide, optimized_schedule)
    equal_daily = apply_weights_over_time(wide, equal_schedule)
    # SPY's own daily return column is already the buy-and-hold benchmark --
    # no portfolio math needed, just the same backtest window
    spy_daily = wide.loc[wide.index >= rebalance_dates[0], "SPY"]

    strategies = {
        "walk_forward_optimized": optimized_daily,
        "equal_weight_rebalanced": equal_daily,
        "spy_buy_and_hold": spy_daily,
    }

    results_rows = []
    summary_rows = []
    for name, daily in strategies.items():
        cum = cumulative_growth(daily)
        for date, value in cum.items():
            results_rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "strategy": name,
                "cumulative_return": round(float(value), 4),
            })
        stats = full_stats(daily)
        summary_rows.append({"strategy": name, **stats})
        logger.info(f"\n{name}:")
        for k, v in stats.items():
            logger.info(f"  {k}: {v}")

    backtest_results = pd.DataFrame(results_rows)
    backtest_summary = pd.DataFrame(summary_rows)

    conn = get_connection()
    init_schema(conn)
    replace_table(conn, "backtest_results", backtest_results)
    replace_table(conn, "backtest_summary", backtest_summary)
    conn.close()
    logger.info(
        f"\nSaved {len(backtest_results):,} rows to 'backtest_results' and "
        f"{len(backtest_summary)} rows to 'backtest_summary'"
    )


if __name__ == "__main__":
    main()
