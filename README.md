# ETF Portfolio Analytics & Strategy Dashboard

I wanted to actually test the stuff you learn in a finance class instead of
just believing what I learned blindly. Does diversification really lower your risk, is
"optimizing" a portfolio actually better than just splitting your money
evenly, and how much could you realistically lose on a bad day? So I built a
small pipeline that pulls 10 years of daily price data for 8 ETFs covering
different asset classes (US stocks, tech, small-cap, international, bonds,
gold, real estate, emerging markets), loads it into a SQL database, and runs
the math myself instead of trusting a textbook answer.

## What it actually does

1. **Pulls the data.** 10 years of daily prices for SPY, QQQ, IWM, EFA, AGG,
   GLD, VNQ, and EEM from Yahoo Finance.
2. **Cleans it up and computes returns.** Daily returns, cumulative growth,
   rolling volatility — the stuff everything else is built on.
3. **Loads it into SQLite** with a real schema (not just pandas dumping a
   table) and runs some of the analysis directly in SQL. This includes a Sharpe
   ratio leaderboard and a max-drawdown calculation done with window functions,
   which I then double-checked against the pandas version to make sure they
   actually agree.
5. **Checks how much each ETF moves with the others.** This is the
   diversification question, if two ETFs move together, holding both
   doesn't really lower your risk.
6. **Finds the "best" portfolio mix.** Using Markowitz optimization (the
   actual math behind "don't put all your eggs in one basket"), I solve for
   the lowest-risk mix and the best risk-adjusted-return mix of these 8 ETFs.
7. **Asks "how bad could it get?"** Monte Carlo simulation and a
   historical-resampling method to estimate how much the portfolio could
   lose on a rough day (Value-at-Risk / Conditional VaR).
8. **Tests whether the optimization would've actually worked in real life.**
   This is the part I think matters most — instead of just optimizing on all
   10 years of data and declaring victory (which is cheating, since you'd
   never have known the future), I re-run the optimization every year using
   only the data available up to that point, and see how it would've
   actually performed going forward.

## What I found (the interesting part)

- **QQQ was the best single ETF on a risk-adjusted basis** (Sharpe ratio of
  0.862), but mixing it with gold (GLD) pushed that even higher, to 0.886, in
  a 67% QQQ / 33% GLD split. So diversification beats just picking the best
  performer, which is exactly the point of doing this instead of guessing.
- **Gold is basically the only real diversifier in this basket.** Its
  correlation with SPY is 0.016 — practically zero. Meanwhile, SPY and QQQ
  move together almost perfectly (0.929 correlation), so holding both
  doesn't actually spread your risk much, even though they're "different"
  ETFs.
- **Just splitting your money evenly across all 8 ETFs already lowered
  volatility below 6 of the 8 individual holdings**, with zero optimization,
  zero analysis, just owning a bit of everything. That's diversification
  doing its job for free.
- **Here's the part that actually surprised me, and I think is the most
  honest finding in the whole project:** when I tested the "optimized"
  portfolio the way you'd actually have to use it — re-optimizing every year
  using only past data, no peeking ahead — it didn't beat a simple
  equal-weight portfolio, and it lost to just buying SPY and holding it
  (Sharpe of 0.573 for the optimized strategy vs. 0.573 for equal-weight vs.
  0.712 for SPY). The optimization looks great when you let it see the whole
  10 years at once, but that's hindsight. Tested honestly, it didn't hold up.
  This is actually a well-known issue with this kind of optimization — it
  tends to fit noise in whatever recent data it's given rather than finding
  something that holds up going forward — and I'd rather show that I found
  it and understand why, than pretend the optimization was a clean win.
- **The "how bad could it get" numbers were worse than a normal bell-curve
  model predicts.** When I estimated worst-case losses using real historical
  data instead of assuming returns follow a clean statistical distribution,
  the worst-case losses came in about 45-50% higher. Markets have fatter
  tails than the simple math assumes.

## How it's built

```
Stage 1  ingest.py      -> pull 10 years of daily prices for the 8 ETFs
Stage 2  transform.py   -> clean it, compute daily/cumulative returns, rolling vol
Stage 3  load_db.py     -> load into SQLite, compute per-ETF risk stats, run the
                           SQL-side analytics (leaderboard + drawdown check)
Stage 4  analyze.py     -> correlation between ETFs, the naive equal-weight portfolio
Stage 6  config.py      -> shared constants every stage imports (no pipeline I/O of its own)
Stage 7  db.py +         -> shared SQLite helpers + the typed schema and window-function
         sql/*.sql          queries that Stage 3 runs
Stage 8  optimize.py    -> the actual portfolio optimization (min-risk & max-Sharpe)
Stage 9  simulate.py    -> Monte Carlo + historical VaR/CVaR
Stage 10 backtest.py    -> the "would this have actually worked" walk-forward test
Stage 5  export.py      -> dumps everything to CSV for the dashboard
```

Stages 6 and 7 aren't steps you run in order like the rest — they're shared
plumbing (config values, database helpers/schema) that Stages 3 onward all
import. Stage numbers otherwise match the order things actually run in: 1
through 4, then 8, 9, 10, then 5 (export) last, once everything else exists
to export.

Each script reads what the one before it produced and writes its own output,
so the whole thing runs top to bottom. Only `ingest.py` actually hits the
internet — everything after that works off the saved data, so I'm not
re-downloading from Yahoo Finance every time I tweak something.

## Built with

- **Python** (pandas, numpy, scipy) for the data work and the optimization
- **SQLite** for storage, but also for real analysis — see `sql/schema.sql`
  and `sql/queries.sql` for the actual SQL doing work, not just storing what
  pandas already computed
- **yfinance** to pull the market data
- **Tableau Public** (dashboard in progress)

## The assumptions I made, so you can judge the numbers fairly

- **The 8 ETFs and date range:** SPY, QQQ, IWM, EFA, AGG, GLD, VNQ, EEM, daily
  data from 2014-01-01 to 2024-01-01.
- **Risk-free rate:** 2% a year, used anywhere I calculate Sharpe or Sortino.
- **252 trading days a year** for annualizing things, and I compound returns
  (not just multiply) when reporting performance — the optimizer itself uses
  simple annualized averages internally, which is the standard way this kind
  of optimization is actually done.
- **No shorting, no leverage.** Every portfolio has to be fully invested with
  non-negative weights — basically, this models a normal person's portfolio,
  not a hedge fund.
- **The backtest rebalances once a year**, using only the trailing 2 years of
  data available at that point — never anything from the future.
- **VaR/CVaR is a 1-day estimate** at 95% and 99% confidence, calculated two
  different ways on purpose, so I could compare a "clean math" assumption
  against what actually happened historically.

## Running it yourself

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

Everything ends up in `data/outputs/` as CSVs, and you can also just open
`data/etf.db` directly with the `sqlite3` CLI (or any SQL tool) and poke
around the tables yourself.

## Dashboard

*Tableau Public link going here once it's built.*

---

Added tests, CI, and a one-command pipeline runner: python pipeline.py
