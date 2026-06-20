# ETF Portfolio Analytics & Strategy Dashboard

A self-contained pipeline that pulls 10 years of daily price history for an
8-ETF, multi-asset-class basket, builds a SQL database around it, and answers
the questions an allocator actually cares about: how risky is each holding,
how much do they diversify each other, what's the best mix of them, how bad
could a bad day get, and would an optimized allocation have actually held up
if you'd run it in real time rather than with hindsight.

## What this answers

- **Which holdings are pulling their weight?** Risk-adjusted return (Sharpe,
  Sortino, Calmar), not just raw return, per ETF.
- **How much does diversification actually help here?** Pairwise correlation
  across the basket, and the volatility reduction from blending all 8 versus
  holding any one.
- **What's the best mix of these 8 holdings?** A Markowitz mean-variance
  optimization — minimum-variance and maximum-Sharpe portfolios, plus the
  full efficient frontier between them.
- **How bad could tomorrow be?** Monte Carlo and historical-bootstrap
  Value-at-Risk / Conditional VaR on the optimized portfolio.
- **Would the optimization have actually worked, or is it hindsight bias?**
  A walk-forward backtest that rebalances annually using only data available
  at the time, scored out-of-sample against equal-weight and SPY benchmarks.

## Key findings

- **QQQ had the best individual risk-adjusted return** of the 8 holdings —
  0.862 Sharpe over 2014-2023 — but **blending it with GLD pushed Sharpe
  higher still, to 0.886**, in a 67%/33% optimized mix. Diversification beat
  picking the single best performer.
- **GLD is the strongest diversifier in the basket**, with a 0.016
  correlation to SPY (essentially zero) versus SPY/QQQ's 0.929 — two ETFs
  that are nearly redundant for risk-reduction purposes despite being
  different tickers.
- **The naive equal-weight portfolio (1/8 in everything) already cut
  volatility below 6 of the 8 individual holdings** (13.7% vs. up to 22.1%
  for IWM) — diversification working exactly as the theory predicts, with no
  optimization required.
- **The honest result: out-of-sample, the optimized portfolio didn't actually
  win.** A walk-forward backtest — re-optimizing annually using only the
  trailing 2 years of data, never peeking ahead — put the optimized
  strategy's Sharpe at 0.573, tied with equal-weight (0.573) and behind plain
  SPY buy-and-hold (0.712). This tracks the well-known critique of
  mean-variance optimization: weights fit to trailing history pick up noise
  in that window more than anything durable. Worth stating plainly rather
  than only reporting the rosier in-sample numbers above.
- **Tail risk is fatter than a normal distribution assumes.** Historical
  bootstrap 99% CVaR came in ~45-50% worse than the parametric Monte Carlo
  estimate for both the equal-weight and max-Sharpe portfolios — the
  portfolios have lost more on their worst days than a normal-distribution
  model would predict.

## Architecture

```
ingest.py      -- pull 10y daily OHLCV for 8 ETFs from Yahoo Finance
   |
transform.py   -- clean prices, compute daily/cumulative returns, rolling vol
   |
load_db.py     -- load into SQLite (typed schema), per-ticker risk metrics,
   |              SQL window-function analytics (Sharpe leaderboard,
   |              SQL-side drawdown cross-check)
   |
analyze.py     -- correlation matrix, naive equal-weight portfolio
   |
optimize.py    -- Markowitz efficient frontier: min-variance & max-Sharpe
   |              portfolios via scipy.optimize
   |
simulate.py    -- Monte Carlo + historical-bootstrap VaR/CVaR
   |
backtest.py    -- walk-forward backtest: optimized vs equal-weight vs SPY
   |
export.py      -- dump every analytical table to CSV for the BI dashboard
```

Each stage reads the previous stage's output and writes its own — `ingest.py`
is the only one that touches the network, so everything downstream is
reproducible from the cached CSVs without hitting Yahoo Finance again.

## Tech stack

- **Python** (pandas, numpy, scipy) — data pipeline and optimization
- **SQLite** — typed schema (`sql/schema.sql`), window-function analytics
  (`sql/queries.sql`): a Sharpe-ratio leaderboard via `RANK()`, and a
  max-drawdown calculation done entirely in SQL via cumulative log-return
  window functions, cross-checked against the pandas calculation
- **yfinance** — market data source
- **Tableau Public** — dashboard (link below, once built)

## Methodology & assumptions

- **Universe:** SPY, QQQ, IWM, EFA, AGG, GLD, VNQ, EEM — 8 ETFs spanning US
  large-cap, tech, small-cap, developed international, US bonds, gold, real
  estate, and emerging markets. 2014-01-01 through 2024-01-01, daily.
- **Risk-free rate:** 2% annual, used in every Sharpe/Sortino calculation.
- **Annualization:** 252 trading days/year; returns compounded
  ((1+mean)^252 - 1), not just multiplied, for reported performance figures.
  The optimizer itself works on simple (non-compounded) annualized mean/
  covariance, the standard Markowitz convention.
- **Optimization constraints:** long-only, fully invested (weights ≥ 0,
  sum to 1) — this models a retail/analyst portfolio, not a fund with
  shorting or leverage.
- **Backtest rebalancing:** annual, using a trailing 2-year lookback window
  that ends strictly before each rebalance date.
- **VaR/CVaR:** 1-day horizon, 95%/99% confidence, computed two ways
  (parametric Monte Carlo and historical bootstrap) so the normal-
  distribution assumption can be checked against what actually happened.

## Running it

```bash
python -m venv .venv
source .venv/Scripts/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cd src
python ingest.py
python transform.py
python load_db.py
python analyze.py
python optimize.py
python simulate.py
python backtest.py
python export.py
```

All outputs land in `data/outputs/` as CSVs, and the full analytical history
is queryable directly from `data/etf.db` with the `sqlite3` CLI or any SQL
client.

## Dashboard

*Tableau Public link: coming soon.*

## What's next

Test coverage and CI are still being added, along with a single-command
pipeline runner — this project is being built in stages over several days
rather than all at once.
