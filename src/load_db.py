"""
Stage 3 — Database load & summary analytics.

Loads the cleaned, return-enriched data into a SQLite database (etf.db) and
computes the headline risk/return metrics per ticker: annualized return,
annualized volatility, Sharpe ratio, and max drawdown. SQLite is used instead of
a hosted database because the whole point of this stage is to demonstrate real
SQL querying (joins, aggregation, window functions) without needing a server —
the .db file is fully portable and anyone can open it with the sqlite3 CLI.
"""

import logging

import pandas as pd
import numpy as np

from config import PROCESSED_DIR, DB_PATH, SQL_DIR, TRADING_DAYS, RISK_FREE_RATE
from db import get_connection, init_schema, replace_table, load_named_queries

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_processed() -> pd.DataFrame:
    path = PROCESSED_DIR / "prices_processed.csv"
    return pd.read_csv(path, parse_dates=["date"])


def build_database(df: pd.DataFrame):
    """Create the schema (if needed) and load the prices table."""
    conn = get_connection()
    init_schema(conn)
    replace_table(conn, "prices", df)
    logger.info(f"Loaded {len(df):,} rows into 'prices' table at {DB_PATH}")
    return conn


def query_summary(conn) -> pd.DataFrame:
    """Use SQL to compute per-ticker summary stats."""
    sql = """
    SELECT
        ticker,
        COUNT(*)                          AS num_days,
        MIN(date)                         AS start_date,
        MAX(date)                         AS end_date,
        AVG(daily_return)                 AS avg_daily_return,
        AVG(volume)                       AS avg_volume
    FROM prices
    WHERE daily_return IS NOT NULL
    GROUP BY ticker
    ORDER BY avg_daily_return DESC;
    """
    return pd.read_sql_query(sql, conn)


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute annualized return, volatility, Sharpe, and max drawdown per ticker."""
    rows = []
    for ticker, g in df.groupby("ticker"):
        g = g.sort_values("date")
        r = g["daily_return"].dropna()

        ann_return = (1 + r.mean()) ** TRADING_DAYS - 1
        ann_vol = r.std() * np.sqrt(TRADING_DAYS)
        sharpe = (ann_return - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else np.nan

        # max drawdown: largest peak-to-trough drop in cumulative return
        cum = (1 + r).cumprod()
        running_max = cum.cummax()
        drawdown = (cum - running_max) / running_max
        max_drawdown = drawdown.min()

        rows.append({
            "ticker": ticker,
            "annual_return": round(ann_return, 4),
            "annual_volatility": round(ann_vol, 4),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_drawdown, 4),
        })
    return pd.DataFrame(rows).sort_values("sharpe_ratio", ascending=False)


def main():
    df = load_processed()
    conn = build_database(df)

    logger.info("\n--- SQL summary query ---")
    summary = query_summary(conn)
    logger.info("\n%s", summary.to_string(index=False))

    logger.info("\n--- Risk / return metrics (pandas) ---")
    metrics = compute_metrics(df)
    logger.info("\n%s", metrics.to_string(index=False))

    # save metrics back into the database as its own table
    replace_table(conn, "metrics", metrics)
    logger.info(f"\nSaved metrics table to {DB_PATH}")

    # Run the window-function analytics from sql/queries.sql so the database
    # is doing real analytical work, not just storing what pandas already
    # computed.
    queries = load_named_queries(SQL_DIR / "queries.sql")

    logger.info("\n--- SQL: Sharpe leaderboard (RANK() window function) ---")
    leaderboard = pd.read_sql_query(queries["sharpe_leaderboard"], conn)
    logger.info("\n%s", leaderboard.to_string(index=False))

    logger.info("\n--- SQL: max drawdown via window functions (cross-check vs. pandas) ---")
    sql_drawdown = pd.read_sql_query(queries["max_drawdown_via_window_functions"], conn)
    logger.info("\n%s", sql_drawdown.to_string(index=False))

    conn.close()


if __name__ == "__main__":
    main()