"""Stage 3: load processed data into a SQLite database and run analytics queries."""

from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "etf.db"

TRADING_DAYS = 252
RISK_FREE_RATE = 0.02  # 2% annual, assumption for Sharpe ratio


def load_processed() -> pd.DataFrame:
    path = PROCESSED_DIR / "prices_processed.csv"
    return pd.read_csv(path, parse_dates=["date"])


def build_database(df: pd.DataFrame):
    """Write the prices table into a fresh SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("prices", conn, if_exists="replace", index=False)
    # an index speeds up queries that filter by ticker
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON prices(ticker);")
    conn.commit()
    print(f"Loaded {len(df):,} rows into 'prices' table at {DB_PATH}")
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

    print("\n--- SQL summary query ---")
    summary = query_summary(conn)
    print(summary.to_string(index=False))

    print("\n--- Risk / return metrics ---")
    metrics = compute_metrics(df)
    print(metrics.to_string(index=False))

    # save metrics back into the database as its own table
    metrics.to_sql("metrics", conn, if_exists="replace", index=False)
    print(f"\nSaved metrics table to {DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()