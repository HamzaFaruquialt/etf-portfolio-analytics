"""Stage 4: correlation matrix and a simple equal-weight portfolio analysis."""

from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "outputs"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "etf.db"

TRADING_DAYS = 252
RISK_FREE_RATE = 0.02


def load_processed() -> pd.DataFrame:
    path = PROCESSED_DIR / "prices_processed.csv"
    return pd.read_csv(path, parse_dates=["date"])


def returns_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot into a date x ticker table of daily returns."""
    wide = df.pivot(index="date", columns="ticker", values="daily_return")
    return wide.dropna()


def correlation_matrix(wide: pd.DataFrame) -> pd.DataFrame:
    """Correlation of daily returns between every pair of ETFs."""
    return wide.corr().round(3)


def equal_weight_portfolio(wide: pd.DataFrame) -> dict:
    """Build an equal-weight portfolio and compute its stats."""
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

    print("--- Correlation matrix ---")
    corr = correlation_matrix(wide)
    print(corr.to_string())
    corr.to_csv(OUTPUT_DIR / "correlation_matrix.csv")

    print("\n--- Equal-weight portfolio ---")
    port = equal_weight_portfolio(wide)
    for k, v in port.items():
        print(f"{k}: {v}")

    # save portfolio stats and write correlation into the db
    conn = sqlite3.connect(DB_PATH)
    corr.to_sql("correlation", conn, if_exists="replace")
    pd.DataFrame([port]).to_sql("portfolio", conn, if_exists="replace", index=False)
    conn.close()
    print(f"\nSaved correlation + portfolio tables to {DB_PATH}")


if __name__ == "__main__":
    main()