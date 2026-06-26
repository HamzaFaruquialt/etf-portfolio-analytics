"""Cross-checks the SQL window-function drawdown query in sql/queries.sql
against the pandas implementation in metrics.py, on a small synthetic
dataset built directly in an in-memory SQLite database -- the two are
expected to agree to floating-point precision.
"""

import sqlite3

import pandas as pd

from config import SQL_DIR
from db import load_named_queries
from metrics import max_drawdown

RETURNS = [0.10, -0.20, 0.10, 0.05, -0.03]


def build_test_db(returns: list[float]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE prices (
            ticker TEXT, date TEXT, adj_close REAL, volume INTEGER,
            daily_return REAL, cumulative_return REAL, rolling_vol_21d REAL
        )
    """)
    dates = pd.date_range("2020-01-01", periods=len(returns), freq="D")
    rows = [
        ("TST", d.strftime("%Y-%m-%d"), None, None, r, None, None)
        for d, r in zip(dates, returns)
    ]
    conn.executemany(
        "INSERT INTO prices (ticker, date, adj_close, volume, daily_return, "
        "cumulative_return, rolling_vol_21d) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


def test_sql_drawdown_matches_pandas_drawdown():
    conn = build_test_db(RETURNS)
    queries = load_named_queries(SQL_DIR / "queries.sql")

    result = pd.read_sql_query(queries["max_drawdown_via_window_functions"], conn)
    sql_drawdown = result.loc[result["ticker"] == "TST", "max_drawdown_sql"].iloc[0]

    expected = max_drawdown(pd.Series(RETURNS))
    assert abs(sql_drawdown - expected) < 1e-9


def test_sharpe_leaderboard_ranks_descending():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE metrics (ticker TEXT, sharpe_ratio REAL)")
    conn.executemany(
        "INSERT INTO metrics (ticker, sharpe_ratio) VALUES (?, ?)",
        [("LOW", 0.1), ("HIGH", 0.9), ("MID", 0.5)],
    )
    conn.commit()

    queries = load_named_queries(SQL_DIR / "queries.sql")
    result = pd.read_sql_query(queries["sharpe_leaderboard"], conn)

    assert result["ticker"].tolist() == ["HIGH", "MID", "LOW"]
    assert result["sharpe_rank"].tolist() == [1, 2, 3]
