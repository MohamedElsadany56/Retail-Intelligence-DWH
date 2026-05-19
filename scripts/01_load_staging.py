from pathlib import Path
import time

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import (
    CORE_FILES,
    CSV_COLUMNS,
    CSV_FILES,
    DATA_DIR,
    ETL_CHUNKSIZE,
    ETL_SCHEMA,
    FORCE_RELOAD_STAGING,
    get_csv_path,
    validate_config,
)
from db import get_engine, run_sql_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_SQL = PROJECT_ROOT / "sql" / "01_schema_staging.sql"

DATE_COLUMNS = {
    "transaction_date",
    "redemption_date",
    "start_date",
    "end_date",
}

TIMESTAMP_COLUMNS = {
    "transaction_timestamp",
    "transaction_datetime",
}

BOOLEAN_COLUMNS = {
    "sales_value_is_possible_outlier",
    "quantity_is_possible_outlier",
    "retail_disc_is_possible_outlier",
    "coupon_disc_is_possible_outlier",
    "quantity_is_invalid",
    "coupon_was_used",
    "retail_discount_was_applied",
}


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def confirm_destructive_reload() -> None:
    tables = ", ".join(CSV_FILES.keys())
    print("FORCE_RELOAD_STAGING=true was detected.")
    print(f"This will truncate these staging tables in schema {ETL_SCHEMA}: {tables}")
    response = input("Type TRUNCATE STAGING to approve this destructive reload: ")
    if response != "TRUNCATE STAGING":
        raise RuntimeError("Staging reload was not approved. Aborting.")


def normalize_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.copy()

    for column in DATE_COLUMNS.intersection(chunk.columns):
        chunk[column] = pd.to_datetime(chunk[column], errors="coerce").dt.date

    for column in TIMESTAMP_COLUMNS.intersection(chunk.columns):
        chunk[column] = pd.to_datetime(chunk[column], errors="coerce")

    for column in BOOLEAN_COLUMNS.intersection(chunk.columns):
        chunk[column] = chunk[column].map(normalize_boolean)

    return chunk.where(pd.notnull(chunk), None)


def normalize_boolean(value):
    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"true", "t", "1", "yes", "y"}:
        return True
    if normalized in {"false", "f", "0", "no", "n"}:
        return False

    return None


def truncate_staging_tables(engine: Engine) -> None:
    confirm_destructive_reload()

    with engine.begin() as conn:
        for table_name in CSV_FILES:
            conn.execute(text(f"TRUNCATE TABLE {ETL_SCHEMA}.{table_name}"))
            print(f"Truncated {ETL_SCHEMA}.{table_name}")


def table_row_count(engine: Engine, table_name: str) -> int:
    with engine.begin() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {ETL_SCHEMA}.{table_name}"))
        return int(result.scalar_one())


def validate_csv_header(table_name: str, file_path: Path) -> None:
    expected_columns = CSV_COLUMNS[table_name]
    actual_columns = list(pd.read_csv(file_path, nrows=0).columns)

    if actual_columns != expected_columns:
        raise RuntimeError(
            "CSV header mismatch for "
            f"{file_path.name}. Expected {expected_columns}, got {actual_columns}"
        )


def count_csv_rows(file_path: Path) -> int:
    with file_path.open("rb") as file:
        line_count = sum(1 for _ in file)

    return max(line_count - 1, 0)


def load_dataframe_chunk(engine: Engine, table_name: str, chunk: pd.DataFrame) -> int:
    normalized_chunk = normalize_chunk(chunk)
    normalized_chunk.to_sql(
        table_name,
        engine,
        schema=ETL_SCHEMA,
        if_exists="append",
        index=False,
    )

    row_count = len(normalized_chunk)
    return row_count


def load_csv_file(engine: Engine, table_name: str, file_path: Path) -> None:
    validate_csv_header(table_name, file_path)

    existing_rows = table_row_count(engine, table_name)
    if existing_rows > 0 and not FORCE_RELOAD_STAGING:
        print(
            f"Skipping {ETL_SCHEMA}.{table_name}: table already has "
            f"{existing_rows:,} rows. Set FORCE_RELOAD_STAGING=true to reload."
        )
        return

    print(f"Loading {file_path.name} into {ETL_SCHEMA}.{table_name}")
    expected_rows = count_csv_rows(file_path)
    total_rows = 0
    table_start_time = time.monotonic()

    reader = pd.read_csv(file_path, chunksize=ETL_CHUNKSIZE)
    for chunk_number, chunk in enumerate(reader, start=1):
        chunk_start_time = time.monotonic()
        loaded_rows = load_dataframe_chunk(engine, table_name, chunk)
        total_rows += loaded_rows
        chunk_elapsed = time.monotonic() - chunk_start_time
        total_elapsed = time.monotonic() - table_start_time

        rows_remaining = max(expected_rows - total_rows, 0)
        rows_per_second = total_rows / total_elapsed if total_elapsed else 0
        estimated_remaining = rows_remaining / rows_per_second if rows_per_second else 0

        print(
            f"Loaded chunk {chunk_number} into {ETL_SCHEMA}.{table_name}: "
            f"{loaded_rows:,} rows this batch, {total_rows:,}/{expected_rows:,} total. "
            f"Batch time: {format_duration(chunk_elapsed)}. "
            f"Elapsed: {format_duration(total_elapsed)}. "
            f"ETA: {format_duration(estimated_remaining)}."
        )

    final_count = table_row_count(engine, table_name)
    total_elapsed = time.monotonic() - table_start_time
    print(
        f"Finished {ETL_SCHEMA}.{table_name}: loaded {total_rows:,} rows "
        f"in {format_duration(total_elapsed)}; table count is {final_count:,}"
    )


def validate_source_files() -> None:
    missing_core_files = [
        file_name for file_name in CORE_FILES if not (DATA_DIR / file_name).exists()
    ]
    if missing_core_files:
        raise FileNotFoundError(f"Missing required core CSV files: {missing_core_files}")


def main() -> None:
    validate_config()
    validate_source_files()

    print(f"Using schema: {ETL_SCHEMA}")
    print(f"Using data directory: {DATA_DIR}")
    print("Connecting to Azure PostgreSQL...")
    engine = get_engine()

    print(f"Creating staging schema and tables from {STAGING_SQL}")
    run_sql_file(engine, STAGING_SQL)

    if FORCE_RELOAD_STAGING:
        truncate_staging_tables(engine)

    for table_name, file_name in CSV_FILES.items():
        file_path = get_csv_path(table_name)
        if not file_path.exists():
            print(f"WARNING: optional file not found, skipping: {file_path}")
            continue

        load_csv_file(engine, table_name, file_path)

    print("Staging load complete. Holiday staging is intentionally not loaded yet.")


if __name__ == "__main__":
    main()
