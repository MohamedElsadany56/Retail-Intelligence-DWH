from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import ETL_SCHEMA, FORCE_RELOAD_FACT, validate_config
from db import get_engine, run_sql_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DWH_SQL = PROJECT_ROOT / "sql" / "02_dimensions_facts.sql"
INDEXES_VIEWS_SQL = PROJECT_ROOT / "sql" / "03_indexes_views.sql"

DIMENSION_TABLES = [
    "dim_household",
    "dim_product",
    "dim_store",
    "dim_date",
    "dim_campaign",
    "dim_coupon",
    "dim_holiday",
]

FACT_TABLES = [
    "fact_transaction_item",
    "fact_coupon_redemption",
    "fact_campaign_participation",
    "fact_product_promotion",
]


def confirm_fact_reload() -> None:
    tables = ", ".join(DIMENSION_TABLES + FACT_TABLES)
    print("FORCE_RELOAD_FACT=true was detected.")
    print(f"This will truncate these DWH tables in schema {ETL_SCHEMA}: {tables}")
    response = input("Type TRUNCATE DWH to approve this destructive reload: ")
    if response != "TRUNCATE DWH":
        raise RuntimeError("DWH reload was not approved. Aborting.")


def run_create_statements_only(engine: Engine) -> None:
    sql = DWH_SQL.read_text(encoding="utf-8")
    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
    create_statements = [
        statement
        for statement in statements
        if statement.upper().startswith("CREATE SCHEMA")
        or statement.upper().startswith("CREATE TABLE")
    ]

    with engine.begin() as conn:
        for statement in create_statements:
            conn.execute(text(statement))


def truncate_dwh_tables(engine: Engine) -> None:
    confirm_fact_reload()
    table_list = ", ".join(
        f"{ETL_SCHEMA}.{table_name}" for table_name in FACT_TABLES + DIMENSION_TABLES
    )

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
        print(f"Truncated DWH tables in schema {ETL_SCHEMA}")


def table_row_count(engine: Engine, table_name: str) -> int:
    with engine.begin() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {ETL_SCHEMA}.{table_name}"))
        return int(result.scalar_one())


def print_table_counts(engine: Engine, table_names: list[str], label: str) -> None:
    print(f"\n{label} row counts")
    for table_name in table_names:
        print(f"- {table_name}: {table_row_count(engine, table_name):,}")


def main() -> None:
    validate_config()

    print(f"Using schema: {ETL_SCHEMA}")
    print("Connecting to Azure PostgreSQL...")
    engine = get_engine()

    if FORCE_RELOAD_FACT:
        run_create_statements_only(engine)
        truncate_dwh_tables(engine)

    print(f"Building dimensions and facts from {DWH_SQL}")
    run_sql_file(engine, DWH_SQL)

    print(f"Creating indexes and analytics views from {INDEXES_VIEWS_SQL}")
    run_sql_file(engine, INDEXES_VIEWS_SQL)

    print_table_counts(engine, DIMENSION_TABLES, "Dimension")
    print_table_counts(engine, FACT_TABLES, "Fact")
    print("\nDWH build complete.")


if __name__ == "__main__":
    main()
