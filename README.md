# ETF Portfolio Analytics & Strategy Dashboard

**Live dashboard: https://hamzafaruquialt.github.io/etf-portfolio-analytics/**

I wanted to actually test the stuff you get taught in a finance class instead of just taking it on faith. Does diversification really lower your risk? Is "optimizing" a portfolio actually better than just splitting your money evenly? And how much could you realistically lose on a bad day? So instead of trusting the textbook answer, I built a pipeline that pulls 10 years of daily prices for 8 ETFs across different asset classes, loads it into a SQL database, and runs the math myself to find out.

The 8 ETFs cover US large-cap (SPY), tech (QQQ), small-cap (IWM), international (EFA), bonds (AGG), gold (GLD), real estate (VNQ), and emerging markets (EEM), basically a spread of everything a normal multi-asset portfolio would hold.

## What it actually does

1. **Pulls the data** — 10 years of daily prices for all 8 ETFs from Yahoo Finance.
2. **Cleans it and computes returns** — daily returns, cumulative growth, and rolling volatility, on which everything downstream is built.
3. **Loads it into SQLite** with a real typed schema (not just pandas dumping a table), and runs some of the analysis directly in SQL, a Sharpe ratio leaderboard and a max-drawdown calc done with window functions, which I then cross-checked against the pandas version to make sure they actually agree.
4. **Checks how much each ETF moves with the others** — this is the diversification question. If two ETFs move together, holding both doesn't really lower your risk.
5. **Finds the "best" portfolio mix** — using Markowitz optimization (the actual math behind "don't put all your eggs in one basket"), I solve for both the lowest-risk mix and the best risk-adjusted-return mix.
6. **Asks "how bad could it get?"** — Monte Carlo simulation plus a historical-resampling method to estimate how much the portfolio could lose on a rough day (Value-at-Risk / Conditional VaR).
7. **Tests whether the optimization would've actually worked in real life** — this is the part I think matters most. Instead of optimizing over all 10 years at once and declaring victory (which is cheating, since you'd never have known the future), I rerun the optimization every year using only the data available up to that point and see how it would've actually performed going forward.

## What I found (the interesting part)

- **QQQ was the best single ETF on a risk-adjusted basis** (Sharpe of 0.862), but mixing it with gold pushed that higher, to 0.886, in a 67% QQQ / 33% GLD split. So diversification beats just picking the best performer, which is the whole point of doing this instead of guessing.

- **Gold is basically the only real diversifier in this basket.** Its correlation with SPY is 0.016 — practically zero. Meanwhile, SPY and QQQ move together almost perfectly (0.929), so holding both doesn't actually spread your risk much, even though they're "different" ETFs.

- **Just splitting money evenly across all 8 ETFs already dropped volatility below 6 of the 8 individual holdings** — zero optimization, zero analysis, just owning a bit of everything. That's diversification doing its job for free.

- **Here's the part that surprised me, and I think it's the most honest finding in the whole project:** when I tested the "optimized" portfolio the way you'd actually have to use it — re-optimizing every year on past data only, no peeking ahead — it didn't beat a simple equal-weight portfolio. It lost to just buying SPY and holding (Sharpe of 0.573 optimized vs. 0.573 equal-weight vs. 0.712 for SPY). The optimization looks great when you let it see all 10 years at once, but that's hindsight. Tested honestly, it didn't hold up. This is actually a well-known issue with this kind of optimization — it tends to fit noise in whatever recent data it's given rather than finding something that holds up going forward — and I'd rather show that I found it and understand why than pretend it was a clean win.

- **The "how bad could it get" numbers were worse than a normal bell-curve model predicts.** When I estimated worst-case losses using real historical data instead of assuming returns follow a clean distribution, the losses came in roughly 45–60% higher, depending on the confidence level. Markets have fatter tails than the simple math assumes.

## How it's built

```
Stage 1   ingest.py      -> pull 10 years of daily prices for the 8 ETFs
Stage 2   transform.py   -> clean it, compute daily/cumulative returns, rolling vol
Stage 3   load_db.py     -> load into SQLite, compute per-ETF risk stats, run the
                            SQL-side analytics (leaderboard + drawdown cross-check)
Stage 4   analyze.py     -> correlation between ETFs, the naive equal-weight portfolio
Stage 8   optimize.py    -> the actual portfolio optimization (min-risk & max-Sharpe)
Stage 9   simulate.py    -> Monte Carlo + historical VaR/CVaR
Stage 10  backtest.py    -> the "would this have actually worked" walk-forward test
Stage 5   export.py      -> dumps everything to CSV for the dashboard

Stage 6   config.py      -> shared constants every stage imports (no I/O of its own)
Stage 7   db.py + sql/*  -> shared SQLite helpers, the typed schema, and the
                            window-function queries Stage 3 runs
```

Stages 6 and 7 aren't steps you run in order like the rest — they're shared plumbing (config values, database helpers, schema) that Stage 3 onward all import. The other numbers match the order things actually run: 1 through 4, then 8, 9, 10, then export last once everything exists to export.

Each script reads what the one before it produced and writes its own output, so the whole thing runs top to bottom. Only `ingest.py` actually hits the internet — everything after works off the saved data, so I'm not re-downloading from Yahoo Finance every time I tweak something. There's also a one-command runner (`python pipeline.py`) that chains all of it together, with `--skip-<stage>` flags so I don't re-pull data on every run.

## Built with

- **Python** (pandas, numpy, scipy) for the data work and the optimization
- **SQLite** for storage, but also for real analysis — see `sql/schema.sql` and `sql/queries.sql` for the actual SQL doing work, not just storing what pandas already computed
- **yfinance** to pull the market data
- **Chart.js** for the live web dashboard above
- **Tableau Public** for a second, more concise view of the same results

## The assumptions I made, so you can judge the numbers fairly

- **The 8 ETFs and date range:** SPY, QQQ, IWM, EFA, AGG, GLD, VNQ, EEM, daily data from 2014-01-01 to 2024-01-01.
- **Risk-free rate:** 2% a year, used anywhere I calculate Sharpe or Sortino.
- **252 trading days a year** for annualizing, and I compound returns (not just multiply) when reporting performance — the optimizer itself uses simple annualized averages internally, which is the standard way this kind of optimization is actually done.
- **No shorting, no leverage.** Every portfolio is fully invested with non-negative weights — this models a normal person's portfolio, not a hedge fund.
- **The backtest rebalances once a year**, using only the trailing 2 years of data available at that point — never anything from the future.
- **VaR/CVaR is a 1-day estimate** at 95% and 99% confidence, calculated two different ways on purpose so I could compare a "clean math" assumption against what actually happened.

## Running it yourself

```bash
python -m venv .venv
source .venv/Scripts/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cd src
python pipeline.py              # runs all stages end to end
```

Or run the stages one at a time (`python ingest.py`, `python transform.py`, and so on, in the order above). Everything ends up in `data/outputs/` as CSVs, and you can open `data/etf.db` directly with the `sqlite3` CLI or any SQL tool to poke around the tables yourself.

## Dashboards

- **Live web dashboard (full deep-dive):** https://hamzafaruquialt.github.io/etf-portfolio-analytics/
- **Tableau Public (concise view):** *link going here once it's built*
