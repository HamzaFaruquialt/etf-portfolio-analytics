"""
Stage 4 — Correlation & naive portfolio analysis.

Computes the pairwise correlation of daily returns across the basket (the key
diversification signal: low/negative correlation between holdings is what
makes a multi-asset portfolio less risky than its individual pieces) and builds
a naive equal-weight (1/N) portfolio as a baseline to compare the optimized
portfolios from Stage 8 against.
"""

import json
import logging

import pandas as pd
import numpy as np

from config import PROCESSED_DIR, OUTPUT_DIR, DB_PATH
from db import get_connection, init_schema, replace_table, upsert_rows
from metrics import full_stats

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_processed() -> pd.DataFrame:
    path = PROCESSED_DIR / "prices_processed.csv"
    return pd.read_csv(path, parse_dates=["date"])


def returns_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot into a date x ticker table of daily returns.

    dropna() keeps only dates where every ticker has a return, so correlation
    and portfolio math are computed on a fair, fully-overlapping sample rather
    than silently comparing mismatched date ranges.
    """
    wide = df.pivot(index="date", columns="ticker", values="daily_return")
    return wide.dropna()


def correlation_matrix(wide: pd.DataFrame) -> pd.DataFrame:
    """Correlation of daily returns between every pair of ETFs.

    Values near 1(perfectly correlated) mean two ETFs move together (little diversification benefit
    from holding both); values near 0 or negative mean they move independently
    or oppositely, which is exactly what reduces blended portfolio risk.
    """
    return wide.corr().round(3)


def tidy_correlation(corr: pd.DataFrame) -> pd.DataFrame:
    """Transform the wide correlation matrix into long form (ticker_a, ticker_b, correlation).

    The database stores this in tidy form (one row per pair) rather than as a
    wide pivot, since a wide table's column count would depend on how many
    tickers are in the universe — see sql/schema.sql for the reasoning.
    """
    long = (
        corr.reset_index()
        .rename(columns={"ticker": "ticker_a"})
        .melt(id_vars="ticker_a", var_name="ticker_b", value_name="correlation")
    )
    return long[["ticker_a", "ticker_b", "correlation"]]


def equal_weight_portfolio(wide: pd.DataFrame) -> dict:
    """Build a naive 1/N portfolio (equal dollars in every ticker) and compute its stats.

    This is the baseline an "optimized" allocation (Stage 8) needs to beat to
    prove the optimization actually adds value over just picking equal weights.
    """
    n = wide.shape[1]
    weights = np.repeat(1 / n, n)
    port_daily = wide.dot(weights)
    weights_dict = dict(zip(wide.columns, weights.round(4).tolist()))

    return {
        "strategy": "equal_weight",
        **full_stats(port_daily),
        "weights_json": json.dumps(weights_dict),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_processed()
    wide = returns_matrix(df)

    logger.info("--- Correlation matrix ---")
    corr = correlation_matrix(wide)
    logger.info("\n%s", corr.to_string())
    corr.to_csv(OUTPUT_DIR / "correlation_matrix.csv")

    logger.info("\n--- Equal-weight portfolio ---")
    port = equal_weight_portfolio(wide)
    for k, v in port.items():
        logger.info(f"{k}: {v}")

    conn = get_connection()
    init_schema(conn)
    # correlation is owned entirely by this stage, so a full replace is safe
    replace_table(conn, "correlation", tidy_correlation(corr))
    # portfolio is shared with optimize.py (Stage 8), which adds its own rows
    # for the max-Sharpe and min-variance strategies — upsert so this run
    # never deletes rows another stage already wrote
    upsert_rows(conn, "portfolio", pd.DataFrame([port]))
    conn.close()
    logger.info(f"\nSaved correlation + portfolio tables to {DB_PATH}")


if __name__ == "__main__":
    main()