"""
Shared risk/return statistics used by Stage 3 (per-ticker metrics), Stage 4
(equal-weight portfolio), and Stage 8 (optimized portfolios).

Keeping these formulas in one place means a ticker's Sharpe ratio and a
portfolio's Sharpe ratio are guaranteed to be computed the same way, so
numbers in the metrics/portfolio/backtest_summary tables are directly
comparable rather than each stage having its own slightly-different formula.
"""

import numpy as np
import pandas as pd

from config import TRADING_DAYS, RISK_FREE_RATE


def annualized_return(daily_returns: pd.Series) -> float:
    """Compounded annual growth rate implied by the average daily return."""
    return (1 + daily_returns.mean()) ** TRADING_DAYS - 1


def annualized_volatility(daily_returns: pd.Series) -> float:
    """Standard deviation of daily returns, scaled to an annual figure."""
    return daily_returns.std() * np.sqrt(TRADING_DAYS)


def cumulative_growth(daily_returns: pd.Series) -> pd.Series:
    """Growth of $1 invested at the start of the series."""
    return (1 + daily_returns).cumprod()


def max_drawdown(daily_returns: pd.Series) -> float:
    """Largest peak-to-trough decline in cumulative growth — the biggest paper
    loss an investor holding from the worst possible entry point would see."""
    cum = cumulative_growth(daily_returns)
    drawdown = (cum - cum.cummax()) / cum.cummax()
    return drawdown.min()


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """Excess return per unit of total volatility (upside and downside alike)."""
    vol = annualized_volatility(daily_returns)
    if not vol:
        return np.nan
    return (annualized_return(daily_returns) - risk_free_rate) / vol


def sortino_ratio(daily_returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """Like Sharpe, but only penalizes downside volatility.

    Investors don't mind upside swings, so dividing by the standard deviation
    of *negative* daily returns alone avoids penalizing an asset for the
    "risk" of occasionally going up a lot.
    """
    downside = daily_returns[daily_returns < 0]
    downside_dev = downside.std() * np.sqrt(TRADING_DAYS)
    if not downside_dev or np.isnan(downside_dev):
        return np.nan
    return (annualized_return(daily_returns) - risk_free_rate) / downside_dev


def calmar_ratio(daily_returns: pd.Series) -> float:
    """Annualized return divided by the worst max drawdown.

    A "return per unit of worst-case pain" measure — popular with allocators
    who care more about the worst realistic loss they'd have sat through than
    about volatility in general.
    """
    mdd = max_drawdown(daily_returns)
    if not mdd:
        return np.nan
    return annualized_return(daily_returns) / abs(mdd)


def full_stats(daily_returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> dict:
    """All headline risk/return stats for one daily-return series, rounded
    for display/storage."""
    return {
        "annual_return": round(annualized_return(daily_returns), 4),
        "annual_volatility": round(annualized_volatility(daily_returns), 4),
        "sharpe_ratio": round(sharpe_ratio(daily_returns, risk_free_rate), 3),
        "sortino_ratio": round(sortino_ratio(daily_returns, risk_free_rate), 3),
        "calmar_ratio": round(calmar_ratio(daily_returns), 3),
        "max_drawdown": round(max_drawdown(daily_returns), 4),
    }
