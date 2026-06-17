"""
Shared settings for the ETF analytics pipeline.

Every other module imports its constants from here instead of redefining them.
Centralizing them means a single change (e.g. adding a ticker, or revisiting the
risk-free rate assumption) propagates everywhere automatically, and there's one
place to look when debugging "why did this number change."
"""

from pathlib import Path

# --- Universe & date range -------------------------------------------------
# 8 ETFs spanning the major asset classes a retail/analyst portfolio would hold:
# US large-cap (SPY), tech (QQQ), small-cap (IWM), developed international (EFA),
# US bonds (AGG), gold (GLD), real estate (VNQ), emerging markets (EEM).
TICKERS = ["SPY", "QQQ", "IWM", "EFA", "AGG", "GLD", "VNQ", "EEM"]
START_DATE = "2014-01-01"
END_DATE = "2024-01-01"

# --- Finance assumptions -----------------------------------------------------
TRADING_DAYS = 252          # standard convention for annualizing daily stats
RISK_FREE_RATE = 0.02       # 2% annual, used as the baseline for Sharpe/Sortino
ROLLING_VOL_WINDOW = 21     # ~1 trading month, used for the rolling volatility column

# --- Monte Carlo VaR/CVaR settings ------------------------------------------
MC_NUM_SIMULATIONS = 10_000
VAR_CONFIDENCE_LEVELS = [0.95, 0.99]

# --- Walk-forward backtest settings ------------------------------------------
BACKTEST_REBALANCE_FREQ = "A"     # pandas offset alias: "A" = annual rebalancing
BACKTEST_LOOKBACK_YEARS = 2       # trailing window used to pick weights at each rebalance

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
SQL_DIR = PROJECT_ROOT / "sql"
DB_PATH = PROJECT_ROOT / "data" / "etf.db"
