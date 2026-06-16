"""Stage 5 prep: export database tables to CSVs for the BI dashboard."""

from pathlib import Path
import sqlite3
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "etf.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "outputs"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    tables = ["prices", "metrics", "correlation", "portfolio"]
    for t in tables:
        df = pd.read_sql_query(f"SELECT * FROM {t};", conn)
        out = OUTPUT_DIR / f"{t}.csv"
        df.to_csv(out, index=False)
        print(f"Exported {t}: {len(df):,} rows -> {out}")

    conn.close()


if __name__ == "__main__":
    main()