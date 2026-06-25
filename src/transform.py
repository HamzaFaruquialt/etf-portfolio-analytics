"""
Stage 2 — Cleaning & feature engineering.

Turns the raw OHLCV dump from ingest.py into the table. Every later stage builds
on: one row per (ticker, date) with daily return, cumulative return, and rolling
volatility already computed. Doing this once here means Stage 3 onward never has
to re-derive returns from raw prices, which is a common source of bugs and inconsistencies.
"""

import logging

import pandas as pd
import numpy as np

from config import RAW_DIR, PROCESSED_DIR, TRADING_DAYS, ROLLING_VOL_WINDOW

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def load_raw() -> pd.DataFrame:
    """Load the raw price CSV produced by ingest.py."""
    path = RAW_DIR / "prices_raw.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Sort, drop bad rows, keep the columns we need."""
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    # keep adjusted close as our price of record
    df = df[["ticker", "date", "adj close", "volume"]]
    df = df.rename(columns={"adj close": "adj_close"})  # for clean convention
    # drop any rows with missing prices
    df = df.dropna(subset=["adj_close"])
    return df


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Add daily returns and rolling volatility per ticker."""
    out = []
    # Loop per ticker, not over the whole table at once, so that returns are
    # always computed within one ETF's own price history. Without this, the
    # last price of one ticker could get differenced against the first price
    # of the next ticker in the table, producing a meaningless "return."
    for ticker, g in df.groupby("ticker"):
        g = g.sort_values("date").copy()
        # daily simple return: (today's price / yesterday's price) - 1
        g["daily_return"] = g["adj_close"].pct_change()
        # cumulative growth of $1 invested at the start — this is what you'd
        # plot to compare how $1 in SPY grew vs. $1 in GLD over the same period
        g["cumulative_return"] = (1 + g["daily_return"]).cumprod()
        # rolling volatility over the trailing window (~1 trading month),
        # scaled by sqrt 252(trading days/year) to express it as an annualized
        # figure — the standard convention so vol numbers are comparable
        # across tickers and against the annualized return later on
        g[f"rolling_vol_{ROLLING_VOL_WINDOW}d"] = (
            g["daily_return"].rolling(ROLLING_VOL_WINDOW).std() * np.sqrt(TRADING_DAYS)
        )
        out.append(g)
    return pd.concat(out, ignore_index=True)


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df = load_raw()
    logger.info(f"Loaded {len(df):,} raw rows")

    df = clean(df)
    logger.info(f"After cleaning: {len(df):,} rows, {df['ticker'].nunique()} tickers")

    df = add_returns(df)
    logger.info(f"Added returns. Columns: {list(df.columns)}")

    out_path = PROCESSED_DIR / "prices_processed.csv"
    df.to_csv(out_path, index=False)
    logger.info(f"Saved processed data to {out_path}")

    # quick sanity check: show first few rows of one ticker
    logger.info("\nSample (SPY):\n%s", df[df["ticker"] == "SPY"].head())


if __name__ == "__main__":
    main()