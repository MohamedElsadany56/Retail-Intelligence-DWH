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

MATERIALIZED_VIEW_COLUMNS = {
    "mv_basket_items": {
        "basket_id",
        "household_id",
        "product_id",
        "department",
        "product_category",
        "product_type",
        "transaction_date",
        "quantity",
        "quantity_capped",
        "sales_value",
        "sales_value_capped",
    },
    "mv_customer_rfm": {
        "household_key",
        "household_id",
        "last_purchase_date",
        "recency_days",
        "frequency_baskets",
        "monetary_value",
    },
    "mv_transaction_analytics": {
        "date_key",
        "full_date",
        "week_of_year",
        "month_number",
        "year_number",
        "store_key",
        "store_id",
        "item_rows",
        "basket_count",
        "household_count",
        "total_quantity",
        "total_sales_value",
        "total_retail_discount",
        "total_coupon_discount",
    },
    "mv_coupon_redemption_analysis": {
        "coupon_key",
        "coupon_upc",
        "product_id",
        "campaign_id",
        "campaign_type",
        "redemption_count",
        "redeeming_households",
        "first_redemption_date",
        "last_redemption_date",
    },
    "mv_campaign_performance": {
        "campaign_key",
        "campaign_id",
        "campaign_type",
        "targeted_households",
        "redeeming_households",
        "redemption_count",
    },
}

LEGACY_MV_COLUMNS = {
    "commodity_desc",
    "sub_commodity_desc",
}


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


def get_existing_materialized_views(engine: Engine) -> set[str]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT matviewname
                FROM pg_matviews
                WHERE schemaname = :schema_name
                """
            ),
            {"schema_name": ETL_SCHEMA},
        )
        return {row.matviewname for row in result}


def get_relation_columns(engine: Engine, relation_name: str) -> set[str]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = :schema_name
                    AND table_name = :relation_name
                """
            ),
            {"schema_name": ETL_SCHEMA, "relation_name": relation_name},
        )
        return {row.column_name for row in result}


def validate_materialized_views_before_build(engine: Engine) -> None:
    existing_views = get_existing_materialized_views(engine)
    incompatible_messages = []

    for view_name, expected_columns in MATERIALIZED_VIEW_COLUMNS.items():
        if view_name not in existing_views:
            continue

        actual_columns = get_relation_columns(engine, view_name)
        missing_columns = expected_columns - actual_columns
        legacy_columns = actual_columns & LEGACY_MV_COLUMNS

        if missing_columns or legacy_columns:
            details = [f"{ETL_SCHEMA}.{view_name} already exists with an incompatible shape."]
            if missing_columns:
                details.append(f"Missing expected columns: {sorted(missing_columns)}.")
            if legacy_columns:
                details.append(f"Legacy columns still present: {sorted(legacy_columns)}.")
            incompatible_messages.append(" ".join(details))

    if incompatible_messages:
        message = "\n".join(incompatible_messages)
        raise RuntimeError(
            f"{message}\n"
            "PostgreSQL will not replace existing materialized views with "
            "CREATE MATERIALIZED VIEW IF NOT EXISTS. Ask for approval before "
            "dropping or replacing these views, then rerun the build."
        )


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

    print("Checking existing materialized views before analytics view build...")
    validate_materialized_views_before_build(engine)

    print(f"Creating indexes and analytics views from {INDEXES_VIEWS_SQL}")
    run_sql_file(engine, INDEXES_VIEWS_SQL)

    print_table_counts(engine, DIMENSION_TABLES, "Dimension")
    print_table_counts(engine, FACT_TABLES, "Fact")
    print("\nDWH build complete.")


if __name__ == "__main__":
    main()
