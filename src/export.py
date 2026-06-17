"""
Stage 5 — Dashboard export.

Dumps every analytical table out of the SQLite database into plain CSVs, so the
BI tool (Tableau Public) never has to query SQLite directly — it just reads flat
files. Keeping this as its own stage means the dashboard's data source is
decoupled from the database engine; the export list grows as later stages
(optimization, simulation, backtest) add new tables.
"""

import logging
import sqlite3

import pandas as pd

from config import DB_PATH, OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TABLES = ["prices", "metrics", "correlation", "portfolio"]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    for t in TABLES:
        df = pd.read_sql_query(f"SELECT * FROM {t};", conn)
        out = OUTPUT_DIR / f"{t}.csv"
        df.to_csv(out, index=False)
        logger.info(f"Exported {t}: {len(df):,} rows -> {out}")

    conn.close()


if __name__ == "__main__":
    main()