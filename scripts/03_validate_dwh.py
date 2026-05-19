from pathlib import Path
import re

import pandas as pd

from config import ETL_SCHEMA, validate_config
from db import get_engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SQL = PROJECT_ROOT / "sql" / "04_validation_queries.sql"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "dwh_validation_report.csv"

VALIDATION_NAME_PATTERN = re.compile(r"--\s*validation:\s*(?P<name>[A-Za-z0-9_]+)")


def load_validation_queries() -> list[tuple[str, str]]:
    sql = VALIDATION_SQL.read_text(encoding="utf-8")
    blocks = [block.strip() for block in sql.split(";") if block.strip()]
    queries = []

    for index, block in enumerate(blocks, start=1):
        match = VALIDATION_NAME_PATTERN.search(block)
        query_name = match.group("name") if match else f"validation_{index}"
        query_sql = VALIDATION_NAME_PATTERN.sub("", block).strip()
        queries.append((query_name, query_sql))

    return queries


def run_validation_queries() -> pd.DataFrame:
    engine = get_engine()
    report_frames = []

    with engine.begin() as conn:
        for query_name, query_sql in load_validation_queries():
            print(f"\n=== {query_name} ===")
            result = pd.read_sql_query(query_sql, conn)

            if result.empty:
                print("No rows returned.")
            else:
                print(result.to_string(index=False))

            result.insert(0, "validation_name", query_name)
            report_frames.append(result)

    if not report_frames:
        return pd.DataFrame(columns=["validation_name"])

    return pd.concat(report_frames, ignore_index=True, sort=False)


def main() -> None:
    validate_config()

    print(f"Using schema: {ETL_SCHEMA}")
    print("Connecting to Azure PostgreSQL...")
    report = run_validation_queries()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUTPUT_PATH, index=False)
    print(f"\nValidation report saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
