from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config import (
    AZURE_DB_HOST,
    AZURE_DB_PASSWORD,
    AZURE_DB_USER,
    ETL_CHUNKSIZE,
    ETL_SCHEMA,
)
from db import get_engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ItemLevel:
    name: str
    column: str
    output_suffix: str


ITEM_LEVELS = {
    "category": ItemLevel("product_category", "product_category", "category"),
    "product_category": ItemLevel("product_category", "product_category", "category"),
    "type": ItemLevel("product_type", "product_type", "type"),
    "product_type": ItemLevel("product_type", "product_type", "type"),
    "product": ItemLevel("product_id", "product_id", "product_id"),
    "product_id": ItemLevel("product_id", "product_id", "product_id"),
}


def validate_database_env() -> None:
    missing = [
        name
        for name, value in {
            "Azure_DB_HOST": AZURE_DB_HOST,
            "Azure_DB_USER": AZURE_DB_USER,
            "Azure_DB_PASSWORD": AZURE_DB_PASSWORD,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing required database environment variables: "
            f"{', '.join(missing)}. Add them to a local .env file."
        )


def quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_PATTERN.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier}")
    return f'"{identifier}"'


def normalize_item_level(item_level: str) -> ItemLevel:
    normalized = item_level.strip().lower()
    if normalized not in ITEM_LEVELS:
        valid_values = ", ".join(sorted(ITEM_LEVELS))
        raise ValueError(f"Unsupported item level '{item_level}'. Use one of: {valid_values}")
    return ITEM_LEVELS[normalized]


def default_output_path(item_level: ItemLevel) -> Path:
    return OUTPUT_DIR / f"basket_items_{item_level.output_suffix}.csv"


def build_basket_item_query(
    *,
    schema_name: str,
    source_table: str,
    item_level: ItemLevel,
    limit_baskets: int | None = None,
) -> str:
    schema_sql = quote_identifier(schema_name)
    table_sql = quote_identifier(source_table)
    item_column_sql = quote_identifier(item_level.column)
    relation = f"{schema_sql}.{table_sql}"

    if limit_baskets is not None:
        if limit_baskets <= 0:
            raise ValueError("--limit-baskets must be greater than zero when provided")

        return f"""
        WITH selected_baskets AS (
            SELECT DISTINCT basket_id
            FROM {relation}
            WHERE basket_id IS NOT NULL
            ORDER BY basket_id
            LIMIT {int(limit_baskets)}
        )
        SELECT DISTINCT
            source.basket_id::TEXT AS basket_id,
            source.{item_column_sql}::TEXT AS item_name
        FROM {relation} AS source
        INNER JOIN selected_baskets AS selected
            ON selected.basket_id = source.basket_id
        WHERE source.basket_id IS NOT NULL
            AND source.{item_column_sql} IS NOT NULL
        """

    return f"""
    SELECT DISTINCT
        basket_id::TEXT AS basket_id,
        {item_column_sql}::TEXT AS item_name
    FROM {relation}
    WHERE basket_id IS NOT NULL
        AND {item_column_sql} IS NOT NULL
    """


def clean_basket_items(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.loc[:, ["basket_id", "item_name"]].copy()
    cleaned["basket_id"] = cleaned["basket_id"].astype("string").str.strip()
    cleaned["item_name"] = cleaned["item_name"].astype("string").str.strip()
    cleaned = cleaned.dropna(subset=["basket_id", "item_name"])
    cleaned = cleaned[(cleaned["basket_id"] != "") & (cleaned["item_name"] != "")]
    cleaned = cleaned.drop_duplicates(["basket_id", "item_name"])
    cleaned = cleaned.sort_values(["basket_id", "item_name"], kind="mergesort")
    return cleaned.reset_index(drop=True)


def load_basket_items_from_postgres(
    *,
    schema_name: str,
    source_table: str,
    item_level: ItemLevel,
    chunksize: int,
    limit_baskets: int | None = None,
) -> pd.DataFrame:
    validate_database_env()
    query = build_basket_item_query(
        schema_name=schema_name,
        source_table=source_table,
        item_level=item_level,
        limit_baskets=limit_baskets,
    )

    engine = get_engine()
    frames: list[pd.DataFrame] = []

    with engine.begin() as conn:
        reader = pd.read_sql_query(text(query), conn, chunksize=chunksize)
        for chunk_number, chunk in enumerate(reader, start=1):
            cleaned_chunk = clean_basket_items(chunk)
            frames.append(cleaned_chunk)
            print(
                f"Loaded chunk {chunk_number}: "
                f"{len(cleaned_chunk):,} distinct basket-item rows"
            )

    if not frames:
        return pd.DataFrame(columns=["basket_id", "item_name"])

    return clean_basket_items(pd.concat(frames, ignore_index=True))


def build_transaction_list(basket_items: pd.DataFrame) -> list[list[str]]:
    transactions = (
        basket_items.groupby("basket_id", sort=False)["item_name"]
        .apply(lambda values: sorted(set(values)))
        .tolist()
    )
    return transactions


def print_preparation_summary(basket_items: pd.DataFrame, transactions: list[list[str]]) -> None:
    row_count = len(basket_items)
    basket_count = basket_items["basket_id"].nunique()
    item_count = basket_items["item_name"].nunique()
    items_per_basket = [len(transaction) for transaction in transactions]
    avg_items = sum(items_per_basket) / len(items_per_basket) if items_per_basket else 0
    max_items = max(items_per_basket) if items_per_basket else 0
    matrix_cells = basket_count * item_count

    print("\nBasket preparation summary")
    print(f"- Basket-item rows: {row_count:,}")
    print(f"- Unique baskets: {basket_count:,}")
    print(f"- Unique items: {item_count:,}")
    print(f"- Avg items per basket: {avg_items:.2f}")
    print(f"- Max items in one basket: {max_items:,}")
    print(f"- Basket-item matrix shape: {basket_count:,} x {item_count:,}")
    print(f"- Potential dense matrix cells: {matrix_cells:,}")
    print(
        "- Matrix note: the mining script builds a sparse one-hot matrix per "
        "support threshold to keep memory usage practical."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a distinct basket-item dataset from Azure PostgreSQL for "
            "association rule mining."
        )
    )
    parser.add_argument(
        "--item-level",
        default="product_category",
        choices=sorted(ITEM_LEVELS),
        help="Mining level to export. Start with product_category before product_type/product_id.",
    )
    parser.add_argument(
        "--schema",
        default=ETL_SCHEMA,
        help="PostgreSQL schema that contains the MBA source table.",
    )
    parser.add_argument(
        "--source-table",
        default="stg_basket_items_for_mba",
        help="Source table or materialized view name inside the selected schema.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="CSV output path. Defaults to outputs/basket_items_<level>.csv.",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=ETL_CHUNKSIZE,
        help="Number of rows to fetch from PostgreSQL per pandas chunk.",
    )
    parser.add_argument(
        "--limit-baskets",
        type=int,
        default=None,
        help="Optional development limit for testing the pipeline on fewer baskets.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    item_level = normalize_item_level(args.item_level)
    output_path = args.output or default_output_path(item_level)
    output_path = output_path if output_path.is_absolute() else PROJECT_ROOT / output_path

    print(f"Using source: {args.schema}.{args.source_table}")
    print(f"Using item level: {item_level.name}")
    print("Connecting to Azure PostgreSQL...")

    basket_items = load_basket_items_from_postgres(
        schema_name=args.schema,
        source_table=args.source_table,
        item_level=item_level,
        chunksize=args.chunksize,
        limit_baskets=args.limit_baskets,
    )

    transactions = build_transaction_list(basket_items)
    print_preparation_summary(basket_items, transactions)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    basket_items.to_csv(output_path, index=False)
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nPrepared basket-item dataset saved to {output_path}")
    print(f"Output file size: {math.ceil(file_size_mb * 100) / 100:.2f} MB")


if __name__ == "__main__":
    main()
