"""
Stage 1 — Ingestion.

Pulls daily historical price history for the ETF basket from Yahoo Finance via
yfinance. This is the only stage that talks to an external data source, so it's
kept small and isolated: every downstream stage works off the CSV this writes,
not off a live API call, which means the rest of the pipeline is reproducible
even if Yahoo Finance is unavailable or the data changes.
"""

import argparse
import logging

import pandas as pd
import yfinance as yf

from config import RAW_DIR, START_DATE, END_DATE, TICKERS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def fetch_ticker(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Download one ETF's daily OHLCV history and tag every row with its ticker."""
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False) # unadjusted prices are more useful for backtesting
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    # yfinance returns a MultiIndex column header when given a single ticker;
    # collapse it back to plain column names like "close", "volume", etc.
    df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(columns=str.lower)
    df.insert(0, "ticker", ticker)
    return df


def fetch_all(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Download every ticker in the basket and stack them into one long table."""
    frames = []
    for ticker in tickers:
        logger.info(f"Fetching {ticker}...")
        frames.append(fetch_ticker(ticker, start, end))
    return pd.concat(frames, ignore_index=True) # don't merge indexes, just stack the rows


def main():
    parser = argparse.ArgumentParser(description="Download daily ETF price history.")
    parser.add_argument("--start", default=START_DATE)
    parser.add_argument("--end", default=END_DATE)
    parser.add_argument("--tickers", nargs="+", default=TICKERS)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    combined = fetch_all(args.tickers, args.start, args.end)

    out_path = RAW_DIR / "prices_raw.csv"
    combined.to_csv(out_path, index=False)
    logger.info(f"Saved {len(combined):,} rows for {combined['ticker'].nunique()} tickers to {out_path}")


if __name__ == "__main__":
    main()
