"""
Stage 5 — Dashboard export.

Dumps every analytical table out of the SQLite database into plain CSVs, so the
BI tool (Tableau Public) never has to query SQLite directly — it just reads flat
files. Keeping this as its own stage means the dashboard's data source is
decoupled from the database engine; the export list grows as later stages
(optimization, simulation, backtest) add new tables.
"""

import json
import logging
import sqlite3

import pandas as pd

from config import DB_PATH, OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TABLES = [
    "prices",
    "metrics",
    "correlation",
    "portfolio",
    "optimization_frontier",
    "var_results",
    "backtest_results",
    "backtest_summary",
]


def build_risk_return_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Combine per-ticker metrics and portfolio-level stats into one tidy
    table with a shared set of columns.

    This is what the dashboard's risk-return scatter plots directly -- it
    puts the 8 individual ETFs and the 3 portfolio strategies (equal-weight,
    min-variance, max-Sharpe) on the same chart, same axes, so you can see at
    a glance whether the optimized portfolios actually sit in a better
    risk-return position than any single holding.
    """
    metrics = pd.read_sql_query(
        "SELECT ticker AS entity, annual_return, annual_volatility, sharpe_ratio, "
        "sortino_ratio, calmar_ratio, max_drawdown FROM metrics",
        conn,
    )
    metrics["category"] = "ETF"

    portfolio = pd.read_sql_query(
        "SELECT strategy AS entity, annual_return, annual_volatility, sharpe_ratio, "
        "sortino_ratio, calmar_ratio, max_drawdown FROM portfolio",
        conn,
    )
    portfolio["category"] = "Portfolio"

    return pd.concat([metrics, portfolio], ignore_index=True)


def build_portfolio_weights(conn: sqlite3.Connection) -> pd.DataFrame:
    """Flatten the `weights_json` column on the `portfolio` table into one
    row per (strategy, ticker, weight).

    weights_json exists as JSON in the database because the number of
    tickers is a config parameter, not a fixed schema (see sql/schema.sql) --
    but Tableau can't parse embedded JSON, so this tidy long-form table is
    what the allocation chart actually reads.
    """
    portfolio = pd.read_sql_query("SELECT strategy, weights_json FROM portfolio", conn)
    rows = []
    for _, row in portfolio.iterrows():
        weights = json.loads(row["weights_json"])
        for ticker, weight in weights.items():
            rows.append({"strategy": row["strategy"], "ticker": ticker, "weight": weight})
    return pd.DataFrame(rows)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    for t in TABLES:
        df = pd.read_sql_query(f"SELECT * FROM {t};", conn)
        out = OUTPUT_DIR / f"{t}.csv"
        df.to_csv(out, index=False)
        logger.info(f"Exported {t}: {len(df):,} rows -> {out}")

    risk_return = build_risk_return_summary(conn)
    out = OUTPUT_DIR / "risk_return_summary.csv"
    risk_return.to_csv(out, index=False)
    logger.info(f"Exported risk_return_summary: {len(risk_return):,} rows -> {out}")

    weights = build_portfolio_weights(conn)
    out = OUTPUT_DIR / "portfolio_weights.csv"
    weights.to_csv(out, index=False)
    logger.info(f"Exported portfolio_weights: {len(weights):,} rows -> {out}")

    conn.close()


if __name__ == "__main__":
    main()