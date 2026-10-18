"""Build the local analytics warehouse and run the SQL analytics layer.

1. Creates data/warehouse.duckdb from sql/schema_setup.sql
2. Loads data/raw/*.csv
3. Runs every `-- name: <id>` query in sql/analytics_queries.sql
   and writes the result to data/processed/<id>.csv

DuckDB is used so the repo runs with zero infrastructure; the SQL is
PostgreSQL-compatible (load the CSVs with psql \\copy to run it on Postgres).
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
DB = ROOT / "data" / "warehouse.duckdb"

TABLES = {  # table -> csv
    "customers": "customers.csv",
    "onboarding": "onboarding.csv",
    "invoices": "invoices.csv",
    "usage_monthly": "usage_monthly.csv",
    "marketing_spend": "marketing_spend.csv",
}


def split_queries(sql_text: str) -> dict[str, str]:
    parts = re.split(r"^-- name:\s*(\w+)\s*$", sql_text, flags=re.M)
    # parts = [preamble, name1, body1, name2, body2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))

    con.execute((ROOT / "sql" / "schema_setup.sql").read_text())
    for table, csv in TABLES.items():
        con.execute(f"INSERT INTO {table} SELECT * FROM read_csv_auto('{RAW / csv}', header=true)")
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"loaded {table:<16} {n:>8,} rows")

    queries = split_queries((ROOT / "sql" / "analytics_queries.sql").read_text())
    for name, sql in queries.items():
        df = con.execute(sql).fetchdf()
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"query  {name:<28} -> {len(df):>6,} rows")
    con.close()


if __name__ == "__main__":
    main()
