-- ============================================================================
-- Stage 7 — Analytical queries (window functions)
-- ============================================================================
-- Each query below is addressed by name from Python via
-- db.load_named_queries(), so this file can be read top-to-bottom like a
-- normal, commented SQL script while still being callable by name.
-- ============================================================================

-- name: sharpe_leaderboard
-- Ranks ETFs by Sharpe ratio using a window function instead of a plain
-- ORDER BY, so ties are handled explicitly and the rank itself is a queryable
-- column (e.g. "show me everything ranked in the top 3").
SELECT
    ticker,
    sharpe_ratio,
    RANK() OVER (ORDER BY sharpe_ratio DESC) AS sharpe_rank
FROM metrics
ORDER BY sharpe_rank;

-- name: rolling_avg_price
-- 21-trading-day moving average of adjusted close, computed natively in SQL.
-- Same lookback window as transform.py's pandas rolling-volatility column —
-- this is the moving-average counterpart, done in SQL to show the rolling
-- window function in `ROWS BETWEEN ... PRECEDING`, not just pandas.rolling().
SELECT
    ticker,
    date,
    adj_close,
    AVG(adj_close) OVER (
        PARTITION BY ticker ORDER BY date
        ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
    ) AS rolling_avg_21d
FROM prices
ORDER BY ticker, date;

-- name: max_drawdown_via_window_functions
-- Recomputes each ticker's max drawdown entirely in SQL, as a cross-check
-- against the pandas calculation in load_db.py's compute_metrics(). The two
-- are expected to match to floating-point precision; test_sql_queries.py
-- asserts this.
--
-- SQLite has no CUMPROD, so cumulative return is rebuilt from log returns:
-- summing ln(1 + daily_return) day-by-day and exponentiating gives the same
-- result as multiplying (1 + daily_return) day-by-day, because
-- exp(sum(ln(x_i))) == product(x_i).
WITH cumulative AS (
    SELECT
        ticker,
        date,
        EXP(SUM(LN(1 + daily_return)) OVER (
            PARTITION BY ticker ORDER BY date
        )) AS cumulative_return
    FROM prices
    WHERE daily_return IS NOT NULL
),
running_peak AS (
    SELECT
        ticker,
        date,
        cumulative_return,
        MAX(cumulative_return) OVER (
            PARTITION BY ticker ORDER BY date
        ) AS peak_return
    FROM cumulative
)
SELECT
    ticker,
    MIN(cumulative_return / peak_return - 1) AS max_drawdown_sql
FROM running_peak
GROUP BY ticker
ORDER BY max_drawdown_sql;
