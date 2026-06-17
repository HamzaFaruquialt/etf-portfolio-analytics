"""
Shared SQLite helpers used by every stage that reads or writes etf.db.

Centralizing connection/schema/table-write logic here means each pipeline
stage just calls these functions instead of re-implementing "open a
connection, make sure the schema exists, write a table" every time, and there
is one place to fix it if the database layer needs to change.
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH, SQL_DIR


def get_connection() -> sqlite3.Connection:
    """Open a connection to the project's SQLite database."""
    return sqlite3.connect(DB_PATH)


def init_schema(conn: sqlite3.Connection) -> None:
    """Create every table the pipeline uses, if it doesn't already exist.

    Tables are declared with explicit types and primary keys in sql/schema.sql
    instead of letting pandas.to_sql silently invent a schema from whatever
    DataFrame happens to be loaded first.
    """
    schema_sql = (SQL_DIR / "schema.sql").read_text()
    conn.executescript(schema_sql)
    conn.commit()


def replace_table(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    """Wipe a table's rows and reload it from a DataFrame, in one transaction.

    Used for tables that exactly one pipeline stage owns end-to-end (prices,
    metrics, correlation). Unlike df.to_sql(if_exists="replace"), this does not
    drop and recreate the table, so the types/primary key from schema.sql
    survive a full pipeline re-run.
    """
    conn.execute(f"DELETE FROM {table}")
    df.to_sql(table, conn, if_exists="append", index=False)
    conn.commit()


def upsert_rows(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    """Insert or replace rows by primary key, leaving other rows untouched.

    Used for tables that multiple stages contribute rows to over time — e.g.
    the `portfolio` table gets an "equal_weight" row from analyze.py (Stage 4)
    and "max_sharpe"/"min_variance" rows from optimize.py (Stage 8). A full
    DELETE+replace here would wipe out whichever stage ran first.
    """
    cols = list(df.columns)
    col_list = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    conn.executemany(sql, df[cols].itertuples(index=False, name=None))
    conn.commit()


def load_named_queries(path: Path) -> dict:
    """Parse a .sql file containing multiple queries marked with `-- name: x`.

    Lets sql/queries.sql read like a normal, commented SQL file while still
    letting Python address each query by name, e.g. queries["sharpe_leaderboard"].
    """
    text = path.read_text()
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    queries = {}
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        sql = parts[i + 1].strip().rstrip(";")
        queries[name] = sql
    return queries
