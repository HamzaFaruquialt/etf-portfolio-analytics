-- ============================================================================
-- Stage 7 — Database schema
-- ============================================================================
-- Tables with a predictable, fixed shape (prices, metrics, correlation,
-- portfolio summaries) are declared here with real column types and primary
-- keys, so the database enforces structure instead of pandas.to_sql silently
-- inventing one from whatever DataFrame happens to load first.
--
-- Two deliberate design choices:
--   1. The correlation matrix is stored in tidy/long form (ticker_a, ticker_b,
--      correlation) rather than as a wide pivot. A wide table's column count
--      depends on how many tickers are in the universe (a pipeline parameter
--      in config.py), which isn't something a fixed schema should depend on.
--   2. Portfolio weight vectors (optimization_frontier, portfolio) are stored
--      as a JSON-encoded TEXT column for the same reason — one column per
--      ticker would tie the schema to TICKERS in config.py.
-- ============================================================================

CREATE TABLE IF NOT EXISTS prices (
    ticker             TEXT    NOT NULL,
    date               TEXT    NOT NULL,
    adj_close          REAL    NOT NULL,
    volume             INTEGER,
    daily_return       REAL,
    cumulative_return  REAL,
    rolling_vol_21d    REAL,
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker);
CREATE INDEX IF NOT EXISTS idx_prices_date   ON prices(date);

-- One row per ETF. sortino_ratio/calmar_ratio are populated by optimize.py
-- (Stage 8); until then they're simply NULL.
CREATE TABLE IF NOT EXISTS metrics (
    ticker             TEXT PRIMARY KEY,
    annual_return      REAL,
    annual_volatility  REAL,
    sharpe_ratio       REAL,
    sortino_ratio      REAL,
    calmar_ratio       REAL,
    max_drawdown       REAL
);

-- Tidy/long correlation matrix: one row per ticker pair.
CREATE TABLE IF NOT EXISTS correlation (
    ticker_a     TEXT NOT NULL,
    ticker_b     TEXT NOT NULL,
    correlation  REAL NOT NULL,
    PRIMARY KEY (ticker_a, ticker_b)
);

-- One row per portfolio strategy. analyze.py (Stage 4) writes the
-- "equal_weight" row; optimize.py (Stage 8) adds "max_sharpe" and
-- "min_variance" rows alongside it without touching the existing row.
CREATE TABLE IF NOT EXISTS portfolio (
    strategy           TEXT PRIMARY KEY,
    annual_return       REAL,
    annual_volatility    REAL,
    sharpe_ratio          REAL,
    sortino_ratio          REAL,
    calmar_ratio            REAL,
    max_drawdown             REAL,
    weights_json             TEXT
);

-- Sweep of the Markowitz efficient frontier (Stage 8): one row per
-- target-return point solved for minimum variance.
CREATE TABLE IF NOT EXISTS optimization_frontier (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    target_return  REAL NOT NULL,
    volatility     REAL NOT NULL,
    sharpe_ratio   REAL,
    weights_json   TEXT NOT NULL
);

-- Monte Carlo / historical-bootstrap VaR and CVaR results (Stage 9).
CREATE TABLE IF NOT EXISTS var_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio   TEXT NOT NULL,
    method      TEXT NOT NULL,
    confidence  REAL NOT NULL,
    var         REAL NOT NULL,
    cvar        REAL NOT NULL
);

-- Walk-forward backtest cumulative performance (Stage 10), in tidy/long form
-- so it's already the exact shape the dashboard's performance line chart needs.
CREATE TABLE IF NOT EXISTS backtest_results (
    date               TEXT NOT NULL,
    strategy           TEXT NOT NULL,
    cumulative_return  REAL NOT NULL,
    PRIMARY KEY (date, strategy)
);

-- Realized out-of-sample stats per backtest strategy (Stage 10).
CREATE TABLE IF NOT EXISTS backtest_summary (
    strategy           TEXT PRIMARY KEY,
    annual_return       REAL,
    annual_volatility    REAL,
    sharpe_ratio          REAL,
    sortino_ratio          REAL,
    calmar_ratio            REAL,
    max_drawdown             REAL
);
