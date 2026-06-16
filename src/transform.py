"""Stage 2: clean raw ETF data and compute returns + rolling metrics."""

from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

TRADING_DAYS = 252  # approx trading days in a year, used to annualize


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
    df = df.rename(columns={"adj close": "adj_close"})
    # drop any rows with missing prices
    df = df.dropna(subset=["adj_close"])
    return df


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Add daily returns and rolling volatility per ticker."""
    out = []
    for ticker, g in df.groupby("ticker"):
        g = g.sort_values("date").copy()
        # daily simple return
        g["daily_return"] = g["adj_close"].pct_change()
        # cumulative growth of $1 invested at the start
        g["cumulative_return"] = (1 + g["daily_return"]).cumprod()
        # 21-day (1 month) rolling volatility, annualized
        g["rolling_vol_21d"] = (
            g["daily_return"].rolling(21).std() * np.sqrt(TRADING_DAYS)
        )
        out.append(g)
    return pd.concat(out, ignore_index=True)


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df = load_raw()
    print(f"Loaded {len(df):,} raw rows")

    df = clean(df)
    print(f"After cleaning: {len(df):,} rows, {df['ticker'].nunique()} tickers")

    df = add_returns(df)
    print(f"Added returns. Columns: {list(df.columns)}")

    out_path = PROCESSED_DIR / "prices_processed.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved processed data to {out_path}")

    # quick sanity check: show first few rows of one ticker
    print("\nSample (SPY):")
    print(df[df["ticker"] == "SPY"].head())


if __name__ == "__main__":
    main()