"""Stage 1: pull historical daily price data for the ETF basket via yfinance."""

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

TICKERS = ["SPY", "QQQ", "IWM", "EFA", "AGG", "GLD", "VNQ", "EEM"]

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_ticker(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(columns=str.lower)
    df.insert(0, "ticker", ticker)
    return df


def fetch_all(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    frames = []
    for ticker in tickers:
        print(f"Fetching {ticker}...")
        frames.append(fetch_ticker(ticker, start, end))
    return pd.concat(frames, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Download daily ETF price history.")
    parser.add_argument("--start", default="2014-01-01")
    parser.add_argument("--end", default="2024-01-01")
    parser.add_argument("--tickers", nargs="+", default=TICKERS)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    combined = fetch_all(args.tickers, args.start, args.end)

    out_path = RAW_DIR / "prices_raw.csv"
    combined.to_csv(out_path, index=False)
    print(f"Saved {len(combined):,} rows for {combined['ticker'].nunique()} tickers to {out_path}")


if __name__ == "__main__":
    main()
