# Tableau Public dashboard spec

This is the build plan for the dashboard — what sheets to make, what each
one reads from, and what it's supposed to show. Build each sheet from the
matching CSV in `data/outputs/` (run `python src/export.py` first, or just
`python src/pipeline.py` to regenerate everything from scratch), then
assemble them into one dashboard and publish to Tableau Public.

## 1. Cumulative performance (line chart)

- **Source:** `backtest_results.csv` (columns: `date`, `strategy`,
  `cumulative_return`)
- **Build:** Line chart, `date` on the x-axis, `cumulative_return` on the
  y-axis, one line per `strategy` (color-coded). Three lines:
  `walk_forward_optimized`, `equal_weight_rebalanced`, `spy_buy_and_hold`.
- **Point of the chart:** This is the honest, out-of-sample result — show
  that the optimized strategy does *not* pull ahead of the simpler
  alternatives. Don't be tempted to swap in the in-sample numbers from
  `portfolio.csv` instead; the out-of-sample comparison is the whole point.

## 2. Risk-return scatter

- **Source:** `risk_return_summary.csv` (columns: `entity`,
  `annual_return`, `annual_volatility`, `sharpe_ratio`, `category`)
- **Build:** Scatter plot, `annual_volatility` on x, `annual_return` on y,
  one point per row, labeled by `entity`, colored by `category` (ETF vs.
  Portfolio) so the 3 portfolio strategies visually stand out from the 8
  individual holdings.
- **Point of the chart:** Shows whether the portfolio strategies sit in a
  better risk-return position than the individual ETFs they're built from —
  `max_sharpe` should sit further up-and-left (more return per unit of risk)
  than most individual ETFs.

## 3. Correlation heatmap

- **Source:** `correlation.csv` (tidy long form: `ticker_a`, `ticker_b`,
  `correlation`)
- **Build:** Heatmap / highlight table, `ticker_a` on rows, `ticker_b` on
  columns, color by `correlation` (diverging color scale, e.g. red at -1,
  white at 0, blue at +1).
- **Point of the chart:** Makes the diversification story visible at a
  glance — SPY/QQQ should be deep blue (0.929), GLD's row/column should be
  pale across the board (near zero against everything else).

## 4. Drawdown over time (area chart)

- **Source:** `backtest_results.csv`, transformed in Tableau: drawdown at
  each date = `cumulative_return` / running MAX(`cumulative_return`) - 1,
  computed per `strategy` using a table calculation (Tableau has a built-in
  "running total"/window function for this — use a `WINDOW_MAX` calculated
  field).
- **Build:** Area chart (or filled line), `date` on x, drawdown % on y, one
  series per `strategy`.
- **Point of the chart:** Shows *when* the worst losses happened (COVID
  crash in 2020 should be visible across all three), and which strategy had
  the deepest, longest drawdowns.

## 5. Efficient frontier

- **Source:** `optimization_frontier.csv` (columns: `target_return`,
  `volatility`, `sharpe_ratio`), plus `portfolio.csv` for the highlighted
  points
- **Build:** Scatter/line plot, `volatility` on x, `target_return` on y, the
  50 frontier points connected as a curve. Overlay the `min_variance` and
  `max_sharpe` rows from `portfolio.csv` as two distinct, labeled marks on
  top of the curve (different shape/color so they stand out from the
  frontier line itself). Optionally add the `equal_weight` point too, sitting
  *inside* the frontier (below/right of it) to visually show it's
  sub-optimal relative to what was achievable.
- **Point of the chart:** The textbook Markowitz picture — and a naive
  portfolio sitting visibly inside the curve instead of on it.

## 6. Optimized allocation (bar or pie)

- **Source:** `portfolio_weights.csv` (tidy long form: `strategy`, `ticker`,
  `weight` — already flattened out of `portfolio.csv`'s `weights_json`
  column by `export.py`, no Tableau-side parsing needed)
- **Build:** Bar chart, one bar group per `strategy`, bars within each group
  = ticker weights. (A grouped bar chart reads more clearly than 3 separate
  pies for comparing 3 strategies side by side.)
- **Point of the chart:** Shows *what* each strategy actually holds —
  e.g. max-Sharpe's concentrated 67% QQQ / 33% GLD vs. min-variance's ~93%
  AGG.

## 7. VaR/CVaR summary

- **Source:** `var_results.csv` (columns: `portfolio`, `method`,
  `confidence`, `var`, `cvar`)
- **Build:** Small grouped bar chart or a simple text/KPI table — `var` and
  `cvar` side by side, grouped by `portfolio` and `method`, faceted by
  `confidence` (95% / 99%).
- **Point of the chart:** Surfaces the fat-tail finding — historical-bootstrap
  CVaR should visibly exceed parametric Monte Carlo CVaR at 99% confidence
  for both portfolios.

## 8. Raw data table

- **Source:** `metrics.csv` (or wire up a sheet selector to also show
  `portfolio.csv`/`backtest_summary.csv`)
- **Build:** A plain sortable/filterable table view — every column from
  `metrics.csv` as-is, no chart, just the grid. This is the "don't trust the
  charts, here are the actual numbers" sheet for anyone who wants to check a
  specific figure without leaving the dashboard.
- **Point of the sheet:** Transparency — not every viewer wants a chart, some
  just want the table. The full pipeline/code/schema still lives on GitHub;
  this is just a convenience view of the headline numbers, not a substitute
  for it.

## Assembling the dashboard

Lay sheets 1-2 at the top (performance + risk-return, the headline story),
3-4 in the middle (diversification + drawdown, the risk story), 5-6 next
(the optimization story), 7 near the bottom (tail risk), and 8 last as a
reference/appendix tab. Add a text box at the top with the one-line pitch
from the README, and a link back to the GitHub repo.
