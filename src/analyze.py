"""
Stage 4 — Correlation & naive portfolio analysis.

Computes the pairwise correlation of daily returns across the basket (the key
diversification signal: low/negative correlation between holdings is what
makes a multi-asset portfolio less risky than its individual pieces) and builds
a naive equal-weight (1/N) portfolio as a baseline to compare the optimized
portfolios from Stage 8 against.
"""

import logging
import sqlite3

import pandas as pd
import numpy as np

from config import PROCESSED_DIR, OUTPUT_DIR, DB_PATH, TRADING_DAYS, RISK_FREE_RATE

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

    Values near 1 mean two ETFs move together (little diversification benefit
    from holding both); values near 0 or negative mean they move independently
    or oppositely, which is exactly what reduces blended portfolio risk.
    """
    return wide.corr().round(3)


def equal_weight_portfolio(wide: pd.DataFrame) -> dict:
    """Build a naive 1/N portfolio (equal dollars in every ticker) and compute its stats.

    This is the baseline an "optimized" allocation (Stage 8) needs to beat to
    prove the optimization actually adds value over just picking equal weights.
    """
    n = wide.shape[1]
    weights = np.repeat(1 / n, n)
    port_daily = wide.dot(weights)

    ann_return = (1 + port_daily.mean()) ** TRADING_DAYS - 1
    ann_vol = port_daily.std() * np.sqrt(TRADING_DAYS)
    sharpe = (ann_return - RISK_FREE_RATE) / ann_vol

    cum = (1 + port_daily).cumprod()
    drawdown = (cum - cum.cummax()) / cum.cummax()
    max_dd = drawdown.min()

    return {
        "annual_return": round(ann_return, 4),
        "annual_volatility": round(ann_vol, 4),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
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

    # save portfolio stats and write correlation into the db
    conn = sqlite3.connect(DB_PATH)
    corr.to_sql("correlation", conn, if_exists="replace")
    pd.DataFrame([port]).to_sql("portfolio", conn, if_exists="replace", index=False)
    conn.close()
    logger.info(f"\nSaved correlation + portfolio tables to {DB_PATH}")


if __name__ == "__main__":
    main()