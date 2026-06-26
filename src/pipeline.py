"""
Stage 11 — Pipeline orchestrator.

Runs every stage end-to-end with one command instead of calling 8 scripts by
hand. Each stage module is still independently runnable on its own (that's
unchanged) -- this just imports each one's main() and calls them in the
order data actually flows through the pipeline.

--skip-<stage> flags exist mainly so iterating on a later stage (say,
optimize.py) doesn't require re-downloading 10 years of price data from
Yahoo Finance on every single run.
"""

import argparse
import logging

import ingest
import transform
import load_db
import analyze
import optimize
import simulate
import backtest
import export

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# (name, callable) in the exact order data flows through the pipeline.
# ingest is wrapped so it gets an empty argv instead of pipeline.py's own
# --skip-* flags, which its own argparse parser doesn't know about.
STAGES = [
    ("ingest", lambda: ingest.main(argv=[])),
    ("transform", transform.main),
    ("load_db", load_db.main),
    ("analyze", analyze.main),
    ("optimize", optimize.main),
    ("simulate", simulate.main),
    ("backtest", backtest.main),
    ("export", export.main),
]


def main():
    parser = argparse.ArgumentParser(description="Run the full ETF analytics pipeline.")
    for name, _ in STAGES:
        parser.add_argument(
            f"--skip-{name}", action="store_true", help=f"Skip the {name} stage"
        )
    args = parser.parse_args()

    for name, run in STAGES:
        if getattr(args, f"skip_{name}"):
            logger.info(f"--- Skipping {name} ---")
            continue
        logger.info(f"\n=== Running {name} ===")
        run()


if __name__ == "__main__":
    main()
