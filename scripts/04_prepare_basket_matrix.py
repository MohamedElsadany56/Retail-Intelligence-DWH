from __future__ import annotations

import argparse
import hashlib
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


def filter_rare_items(
    basket_items: pd.DataFrame,
    *,
    min_item_frequency: int,
) -> tuple[pd.DataFrame, int]:
    """Drop items that appear in fewer than ``min_item_frequency`` basket-item rows.

    Rare items add noise and slow the algorithms without producing stable rules.
    Filtering is applied AFTER deduplication so each (basket, item) pair counts once.
    Returns the filtered frame and the count of items that were removed.
    """
    if min_item_frequency <= 1:
        return basket_items, 0

    item_counts = basket_items["item_name"].value_counts()
    kept_items = set(item_counts[item_counts >= min_item_frequency].index)
    removed_item_count = int(len(item_counts) - len(kept_items))

    if not removed_item_count:
        return basket_items, 0

    filtered = basket_items[basket_items["item_name"].isin(kept_items)].reset_index(drop=True)
    return filtered, removed_item_count


def split_baskets_train_test(
    basket_items: pd.DataFrame,
    *,
    test_size: float,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hash-based deterministic train/test split on basket_id.

    Using a hash keeps the split stable across runs and across chunked reads,
    while still respecting ``random_state`` (the seed feeds the hash). We split
    on whole baskets so a basket is never partly seen, partly hidden.
    """
    if not 0.0 < test_size < 1.0:
        raise ValueError("--test-size must be between 0 and 1 (exclusive)")

    unique_baskets = basket_items["basket_id"].drop_duplicates().reset_index(drop=True)
    seed_bytes = str(random_state).encode("utf-8")

    def is_test(basket_id: str) -> bool:
        digest = hashlib.md5(seed_bytes + str(basket_id).encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        return bucket < test_size

    test_basket_ids = set(unique_baskets[unique_baskets.map(is_test)].tolist())

    train_df = basket_items[~basket_items["basket_id"].isin(test_basket_ids)].reset_index(drop=True)
    test_df = basket_items[basket_items["basket_id"].isin(test_basket_ids)].reset_index(drop=True)
    return train_df, test_df


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


def print_preparation_summary(
    basket_items: pd.DataFrame,
    transactions: list[list[str]],
    *,
    label: str = "Basket preparation summary",
) -> None:
    row_count = len(basket_items)
    basket_count = basket_items["basket_id"].nunique()
    item_count = basket_items["item_name"].nunique()
    items_per_basket = [len(transaction) for transaction in transactions]
    avg_items = sum(items_per_basket) / len(items_per_basket) if items_per_basket else 0
    max_items = max(items_per_basket) if items_per_basket else 0
    matrix_cells = basket_count * item_count

    print(f"\n{label}")
    print(f"- Basket-item rows: {row_count:,}")
    print(f"- Unique baskets: {basket_count:,}")
    print(f"- Unique items: {item_count:,}")
    print(f"- Avg items per basket: {avg_items:.2f}")
    print(f"- Max items in one basket: {max_items:,}")
    print(f"- Basket-item matrix shape: {basket_count:,} x {item_count:,}")
    print(f"- Potential dense matrix cells: {matrix_cells:,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a distinct basket-item dataset from Azure PostgreSQL for "
            "association rule mining. Optionally filters rare items and "
            "produces a deterministic train/test split for recommendation evaluation."
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
    parser.add_argument(
        "--min-item-frequency",
        type=int,
        default=1,
        help=(
            "Drop items that appear in fewer than this many basket-item rows. "
            "Use 1 to keep everything (default). A typical product-level value "
            "is around 50 to control runtime and noise."
        ),
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.0,
        help=(
            "Fraction of baskets to hold out for the recommendation evaluation "
            "step. Use 0.0 (default) to keep the legacy single-file output, or "
            "0.2 to write basket_items_<level>_train.csv and basket_items_<level>_test.csv."
        ),
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Seed used by the deterministic basket train/test split.",
    )
    return parser.parse_args()


def write_basket_csv(df: pd.DataFrame, output_path: Path, *, label: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n{label} saved to {output_path}")
    print(f"Output file size: {math.ceil(file_size_mb * 100) / 100:.2f} MB")


def main() -> None:
    args = parse_args()
    item_level = normalize_item_level(args.item_level)
    output_path = args.output or default_output_path(item_level)
    output_path = output_path if output_path.is_absolute() else PROJECT_ROOT / output_path

    print(f"Using source: {args.schema}.{args.source_table}")
    print(f"Using item level: {item_level.name}")
    print(f"Minimum item frequency: {args.min_item_frequency}")
    print(f"Test split: {args.test_size:.2f} (random_state={args.random_state})")
    print("Connecting to Azure PostgreSQL...")

    basket_items = load_basket_items_from_postgres(
        schema_name=args.schema,
        source_table=args.source_table,
        item_level=item_level,
        chunksize=args.chunksize,
        limit_baskets=args.limit_baskets,
    )

    if args.min_item_frequency > 1:
        before_rows = len(basket_items)
        before_items = basket_items["item_name"].nunique()
        basket_items, removed = filter_rare_items(
            basket_items,
            min_item_frequency=args.min_item_frequency,
        )
        print(
            f"\nRare-item filter (min_item_frequency={args.min_item_frequency}): "
            f"removed {removed:,} items, dropped {before_rows - len(basket_items):,} basket-item rows, "
            f"kept {basket_items['item_name'].nunique():,} of {before_items:,} items."
        )

    transactions = build_transaction_list(basket_items)
    print_preparation_summary(basket_items, transactions, label="Full prepared dataset summary")

    if args.test_size > 0.0:
        train_df, test_df = split_baskets_train_test(
            basket_items,
            test_size=args.test_size,
            random_state=args.random_state,
        )

        train_transactions = build_transaction_list(train_df)
        test_transactions = build_transaction_list(test_df)

        print_preparation_summary(train_df, train_transactions, label="Train split summary")
        print_preparation_summary(test_df, test_transactions, label="Test split summary")

        train_path = output_path.with_name(f"{output_path.stem}_train{output_path.suffix}")
        test_path = output_path.with_name(f"{output_path.stem}_test{output_path.suffix}")

        write_basket_csv(basket_items, output_path, label="Full prepared basket-item dataset")
        write_basket_csv(train_df, train_path, label="Train basket-item dataset")
        write_basket_csv(test_df, test_path, label="Test basket-item dataset")
    else:
        write_basket_csv(basket_items, output_path, label="Prepared basket-item dataset")


if __name__ == "__main__":
    main()
