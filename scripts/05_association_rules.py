from __future__ import annotations

import argparse
import itertools
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from performance_utils import (
    PERFORMANCE_COLUMNS,
    build_performance_row,
    measure_performance,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

RULE_EXPORT_COLUMNS = [
    "algorithm_name",
    "item_level",
    "min_support",
    "min_confidence",
    "antecedents",
    "consequents",
    "antecedent_count",
    "consequent_count",
    "support_count",
    "antecedent_support",
    "consequent_support",
    "support",
    "confidence",
    "lift",
    "leverage",
    "conviction",
]

ITEM_LEVEL_SUFFIXES = {
    "category": ("product_category", "category"),
    "product_category": ("product_category", "category"),
    "type": ("product_type", "type"),
    "product_type": ("product_type", "type"),
    "product": ("product_id", "product_id"),
    "product_id": ("product_id", "product_id"),
}

def normalize_item_level(item_level: str) -> tuple[str, str]:
    normalized = item_level.strip().lower()
    if normalized not in ITEM_LEVEL_SUFFIXES:
        valid_values = ", ".join(sorted(ITEM_LEVEL_SUFFIXES))
        raise ValueError(f"Unsupported item level '{item_level}'. Use one of: {valid_values}")
    return ITEM_LEVEL_SUFFIXES[normalized]


def default_input_path(item_level: str) -> Path:
    _, suffix = normalize_item_level(item_level)
    return OUTPUT_DIR / f"basket_items_{suffix}.csv"


def parse_float_list(raw_value: str) -> list[float]:
    values = [float(value.strip()) for value in raw_value.split(",") if value.strip()]
    if not values:
        raise ValueError("At least one numeric threshold is required.")
    return values


def parse_algorithm_list(raw_value: str) -> list[str]:
    allowed = {"apriori", "fpgrowth", "eclat"}
    algorithms = [value.strip().lower() for value in raw_value.split(",") if value.strip()]
    unknown = sorted(set(algorithms) - allowed)
    if unknown:
        raise ValueError(f"Unsupported algorithm(s): {', '.join(unknown)}")
    return algorithms


def load_prepared_basket_items(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Prepared basket dataset not found: {input_path}. "
            "Run scripts/04_prepare_basket_matrix.py first."
        )

    basket_items = pd.read_csv(input_path, dtype={"basket_id": "string", "item_name": "string"})
    required_columns = {"basket_id", "item_name"}
    missing_columns = required_columns - set(basket_items.columns)
    if missing_columns:
        raise ValueError(
            f"{input_path} is missing required columns: {sorted(missing_columns)}"
        )

    basket_items = basket_items.loc[:, ["basket_id", "item_name"]].copy()
    basket_items["basket_id"] = basket_items["basket_id"].astype("string").str.strip()
    basket_items["item_name"] = basket_items["item_name"].astype("string").str.strip()
    basket_items = basket_items.dropna(subset=["basket_id", "item_name"])
    basket_items = basket_items[
        (basket_items["basket_id"] != "") & (basket_items["item_name"] != "")
    ]
    basket_items = basket_items.drop_duplicates(["basket_id", "item_name"])
    return basket_items.reset_index(drop=True)


def input_stats(basket_items: pd.DataFrame) -> dict[str, int]:
    return {
        "input_row_count": int(len(basket_items)),
        "input_basket_count": int(basket_items["basket_id"].nunique()),
        "input_item_count": int(basket_items["item_name"].nunique()),
    }


def build_transactions(basket_items: pd.DataFrame) -> list[tuple[str, ...]]:
    transactions = (
        basket_items.groupby("basket_id", sort=False)["item_name"]
        .apply(lambda values: tuple(sorted(set(str(value) for value in values))))
        .tolist()
    )
    return [transaction for transaction in transactions if transaction]


def min_support_count(min_support: float, basket_count: int) -> int:
    return max(1, math.ceil(min_support * basket_count))


def support_lookup_to_frame(
    support_lookup: dict[frozenset[str], int],
    *,
    basket_count: int,
) -> pd.DataFrame:
    if not support_lookup:
        return pd.DataFrame(columns=["support", "itemsets", "support_count"])

    records = [
        {
            "support": support_count / basket_count if basket_count else 0.0,
            "itemsets": itemset,
            "support_count": support_count,
        }
        for itemset, support_count in support_lookup.items()
    ]
    return pd.DataFrame(records, columns=["support", "itemsets", "support_count"])


def empty_rules_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "antecedents",
            "consequents",
            "antecedent_count",
            "consequent_count",
            "support_count",
            "antecedent support",
            "consequent support",
            "support",
            "confidence",
            "lift",
            "leverage",
            "conviction",
        ]
    )


def combine_performance(
    mining_perf: dict[str, float],
    rule_perf: dict[str, float] | None = None,
) -> dict[str, float]:
    rule_perf = rule_perf or {}
    return {
        "runtime_seconds": round(
            mining_perf.get("runtime_seconds", 0.0)
            + rule_perf.get("runtime_seconds", 0.0),
            4,
        ),
        "memory_usage_mb": rule_perf.get(
            "memory_usage_mb",
            mining_perf.get("memory_usage_mb", 0.0),
        ),
        "memory_delta_mb": round(
            mining_perf.get("memory_delta_mb", 0.0)
            + rule_perf.get("memory_delta_mb", 0.0),
            4,
        ),
    }


def format_itemset(itemset) -> str:
    return " | ".join(sorted(str(item) for item in itemset))


def format_rules_for_export(
    rules: pd.DataFrame,
    *,
    algorithm_name: str,
    item_level: str,
    min_support: float,
    min_confidence: float,
) -> pd.DataFrame:
    if rules.empty:
        return pd.DataFrame(columns=RULE_EXPORT_COLUMNS)

    formatted = pd.DataFrame()
    formatted["algorithm_name"] = algorithm_name
    formatted["item_level"] = item_level
    formatted["min_support"] = min_support
    formatted["min_confidence"] = min_confidence
    formatted["antecedents"] = rules["antecedents"].map(format_itemset)
    formatted["consequents"] = rules["consequents"].map(format_itemset)
    formatted["antecedent_count"] = rules.get("antecedent_count", 0)
    formatted["consequent_count"] = rules.get("consequent_count", 0)
    formatted["support_count"] = rules.get("support_count", 0)
    formatted["antecedent_support"] = rules["antecedent support"]
    formatted["consequent_support"] = rules["consequent support"]
    formatted["support"] = rules["support"]
    formatted["confidence"] = rules["confidence"]
    formatted["lift"] = rules["lift"]
    formatted["leverage"] = rules.get("leverage", float("nan"))
    formatted["conviction"] = rules.get("conviction", float("nan"))
    return formatted.loc[:, RULE_EXPORT_COLUMNS]


def generate_rules_from_supports(
    support_lookup: dict[frozenset[str], int],
    *,
    basket_count: int,
    min_confidence: float,
) -> pd.DataFrame:
    rows: list[dict] = []

    for itemset, support_count in support_lookup.items():
        if len(itemset) < 2:
            continue

        items = tuple(sorted(itemset))
        for antecedent_size in range(1, len(items)):
            for antecedent_tuple in itertools.combinations(items, antecedent_size):
                antecedent = frozenset(antecedent_tuple)
                consequent = itemset - antecedent

                antecedent_count = support_lookup.get(antecedent)
                consequent_count = support_lookup.get(consequent)
                if not antecedent_count or not consequent_count:
                    continue

                confidence = support_count / antecedent_count
                if confidence < min_confidence:
                    continue

                support = support_count / basket_count if basket_count else 0.0
                antecedent_support = antecedent_count / basket_count if basket_count else 0.0
                consequent_support = consequent_count / basket_count if basket_count else 0.0
                lift = confidence / consequent_support if consequent_support else 0.0
                leverage = support - (antecedent_support * consequent_support)
                conviction = (
                    math.inf
                    if math.isclose(confidence, 1.0)
                    else (1 - consequent_support) / (1 - confidence)
                )

                rows.append(
                    {
                        "antecedents": antecedent,
                        "consequents": consequent,
                        "antecedent_count": antecedent_count,
                        "consequent_count": consequent_count,
                        "support_count": support_count,
                        "antecedent support": antecedent_support,
                        "consequent support": consequent_support,
                        "support": support,
                        "confidence": confidence,
                        "lift": lift,
                        "leverage": leverage,
                        "conviction": conviction,
                    }
                )

    if not rows:
        return empty_rules_df()

    return pd.DataFrame(rows).sort_values(
        ["lift", "confidence", "support"],
        ascending=[False, False, False],
    )


def generate_apriori_candidates(
    previous_level: set[tuple[str, ...]],
    itemset_size: int,
) -> set[tuple[str, ...]]:
    previous_sorted = sorted(previous_level)
    candidates: set[tuple[str, ...]] = set()

    for left_index, left in enumerate(previous_sorted):
        for right in previous_sorted[left_index + 1 :]:
            if left[: itemset_size - 2] != right[: itemset_size - 2]:
                break

            candidate = tuple(sorted(set(left) | set(right)))
            if len(candidate) != itemset_size:
                continue

            if all(
                tuple(subset) in previous_level
                for subset in itertools.combinations(candidate, itemset_size - 1)
            ):
                candidates.add(candidate)

    return candidates


def mine_apriori_frequent_itemsets(
    transactions: list[tuple[str, ...]],
    *,
    basket_count: int,
    min_support: float,
    max_itemset_size: int,
) -> tuple[dict[frozenset[str], int], str]:
    threshold = min_support_count(min_support, basket_count)
    item_counts = Counter(
        item for transaction in transactions for item in transaction
    )
    current_level = {
        (item,): count
        for item, count in item_counts.items()
        if count >= threshold
    }
    support_lookup: dict[frozenset[str], int] = {
        frozenset(itemset): count for itemset, count in current_level.items()
    }

    for itemset_size in range(2, max_itemset_size + 1):
        previous_level = set(current_level)
        if not previous_level:
            break

        candidates = generate_apriori_candidates(previous_level, itemset_size)
        if not candidates:
            break

        candidate_counts: Counter[tuple[str, ...]] = Counter()
        for transaction in transactions:
            if len(transaction) < itemset_size:
                continue
            for candidate in itertools.combinations(transaction, itemset_size):
                if candidate in candidates:
                    candidate_counts[candidate] += 1

        current_level = {
            itemset: count
            for itemset, count in candidate_counts.items()
            if count >= threshold
        }
        support_lookup.update(
            {frozenset(itemset): count for itemset, count in current_level.items()}
        )

    note = (
        f"Pure-Python Apriori used {len(transactions):,} transactions with "
        f"support count >= {threshold:,}."
    )
    return support_lookup, note


class FPNode:
    def __init__(self, item: str | None, count: int, parent: "FPNode | None"):
        self.item = item
        self.count = count
        self.parent = parent
        self.children: dict[str, FPNode] = {}
        self.link: FPNode | None = None


def append_header_link(header_table: dict[str, dict], item: str, node: FPNode) -> None:
    header = header_table[item]
    if header["head"] is None:
        header_table[item]["head"] = node
        header_table[item]["tail"] = node
        return

    header["tail"].link = node
    header["tail"] = node


def insert_fp_transaction(
    root: FPNode,
    header_table: dict[str, dict],
    transaction: list[str],
    count: int,
) -> None:
    current = root
    for item in transaction:
        child = current.children.get(item)
        if child is None:
            child = FPNode(item=item, count=0, parent=current)
            current.children[item] = child
            append_header_link(header_table, item, child)
        child.count += count
        current = child


def build_fp_tree_from_weighted_transactions(
    weighted_transactions: list[tuple[list[str], int]],
    *,
    min_support_count_value: int,
) -> tuple[FPNode | None, dict[str, dict], dict[str, int]]:
    item_counts: Counter[str] = Counter()
    for transaction, count in weighted_transactions:
        for item in transaction:
            item_counts[item] += count

    frequent_counts = {
        item: count
        for item, count in item_counts.items()
        if count >= min_support_count_value
    }
    if not frequent_counts:
        return None, {}, {}

    rank = {
        item: index
        for index, (item, _) in enumerate(
            sorted(frequent_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        )
    }
    header_table = {
        item: {"support_count": count, "head": None, "tail": None}
        for item, count in frequent_counts.items()
    }
    root = FPNode(item=None, count=0, parent=None)

    for transaction, count in weighted_transactions:
        ordered = sorted(
            (item for item in transaction if item in frequent_counts),
            key=lambda item: rank[item],
        )
        if ordered:
            insert_fp_transaction(root, header_table, ordered, count)

    return root, header_table, frequent_counts


def build_conditional_pattern_base(node: FPNode | None) -> list[tuple[list[str], int]]:
    patterns: list[tuple[list[str], int]] = []
    while node is not None:
        path: list[str] = []
        parent = node.parent
        while parent is not None and parent.item is not None:
            path.append(parent.item)
            parent = parent.parent
        if path:
            patterns.append((list(reversed(path)), node.count))
        node = node.link
    return patterns


def mine_fp_tree(
    header_table: dict[str, dict],
    *,
    min_support_count_value: int,
    max_itemset_size: int,
    suffix: tuple[str, ...],
    support_lookup: dict[frozenset[str], int],
) -> None:
    items = sorted(
        header_table,
        key=lambda item: (header_table[item]["support_count"], item),
    )

    for item in items:
        new_itemset = tuple(sorted((item,) + suffix))
        support_lookup[frozenset(new_itemset)] = header_table[item]["support_count"]

        if len(new_itemset) >= max_itemset_size:
            continue

        conditional_patterns = build_conditional_pattern_base(header_table[item]["head"])
        conditional_root, conditional_header, _ = build_fp_tree_from_weighted_transactions(
            conditional_patterns,
            min_support_count_value=min_support_count_value,
        )
        if conditional_root is not None and conditional_header:
            mine_fp_tree(
                conditional_header,
                min_support_count_value=min_support_count_value,
                max_itemset_size=max_itemset_size,
                suffix=new_itemset,
                support_lookup=support_lookup,
            )


def mine_fpgrowth_frequent_itemsets(
    transactions: list[tuple[str, ...]],
    *,
    basket_count: int,
    min_support: float,
    max_itemset_size: int,
) -> tuple[dict[frozenset[str], int], str]:
    threshold = min_support_count(min_support, basket_count)
    weighted_transactions = [(list(transaction), 1) for transaction in transactions]
    root, header_table, _ = build_fp_tree_from_weighted_transactions(
        weighted_transactions,
        min_support_count_value=threshold,
    )

    support_lookup: dict[frozenset[str], int] = {}
    if root is not None and header_table:
        mine_fp_tree(
            header_table,
            min_support_count_value=threshold,
            max_itemset_size=max_itemset_size,
            suffix=tuple(),
            support_lookup=support_lookup,
        )

    note = (
        f"Pure-Python FP-Growth used {len(transactions):,} transactions with "
        f"support count >= {threshold:,}."
    )
    return support_lookup, note


def run_frequent_itemset_algorithm(
    *,
    algorithm_name: str,
    miner,
    transactions: list[tuple[str, ...]],
    item_level: str,
    min_supports: list[float],
    min_confidences: list[float],
    max_itemset_size: int,
    stats: dict[str, int],
) -> tuple[pd.DataFrame, list[dict]]:
    exported_rules: list[pd.DataFrame] = []
    comparison_rows: list[dict] = []

    for min_support in min_supports:
        support_notes: list[str] = [
            "Frequent itemsets mined once per support threshold and reused "
            "across confidence thresholds."
        ]
        support_lookup: dict[frozenset[str], int] = {}
        frequent_itemset_count = 0
        mining_perf: dict[str, float] = {}
        mining_failed = False

        print(f"{algorithm_name} mining support={min_support}...", flush=True)
        try:
            with measure_performance() as mining_perf:
                support_lookup, mining_note = miner(
                    transactions,
                    basket_count=stats["input_basket_count"],
                    min_support=min_support,
                    max_itemset_size=max_itemset_size,
                )
                support_notes.append(mining_note)
                frequent_itemset_count = len(support_lookup)
        except Exception as exc:
            support_notes.append(f"FAILED: {exc}")
            mining_failed = True
            frequent_itemset_count = 0

        for min_confidence in min_confidences:
            rules = empty_rules_df()
            rule_perf: dict[str, float] = {}
            notes = support_notes.copy()

            if not mining_failed:
                print(
                    f"{algorithm_name} rules support={min_support} "
                    f"confidence={min_confidence}...",
                    flush=True,
                )
                try:
                    with measure_performance() as rule_perf:
                        rules = generate_rules_from_supports(
                            support_lookup,
                            min_confidence=min_confidence,
                            basket_count=stats["input_basket_count"],
                        )
                except Exception as exc:
                    notes.append(f"FAILED: {exc}")

            perf = combine_performance(mining_perf, rule_perf)

            exported_rules.append(
                format_rules_for_export(
                    rules,
                    algorithm_name=algorithm_name,
                    item_level=item_level,
                    min_support=min_support,
                    min_confidence=min_confidence,
                )
            )
            comparison_rows.append(
                build_performance_row(
                    algorithm_name=algorithm_name,
                    item_level=item_level,
                    min_support=min_support,
                    min_confidence=min_confidence,
                    frequent_itemset_count=frequent_itemset_count,
                    rules_df=rules,
                    perf=perf,
                    input_row_count=stats["input_row_count"],
                    input_basket_count=stats["input_basket_count"],
                    input_item_count=stats["input_item_count"],
                    notes=" | ".join(notes),
                )
            )

            print(
                f"{algorithm_name} support={min_support} confidence={min_confidence}: "
                f"{frequent_itemset_count:,} itemsets, {len(rules):,} rules",
                flush=True,
            )

    rules_df = concat_or_empty(exported_rules, RULE_EXPORT_COLUMNS)
    return rules_df, comparison_rows


def build_vertical_itemsets(
    basket_items: pd.DataFrame,
    *,
    min_support: float,
    basket_count: int,
) -> tuple[list[tuple[str, set[str]]], int]:
    min_support_count = max(1, math.ceil(min_support * basket_count))

    vertical: dict[str, set[str]] = {}
    for basket_id, item_name in basket_items[["basket_id", "item_name"]].itertuples(index=False):
        vertical.setdefault(str(item_name), set()).add(str(basket_id))

    frequent_vertical = [
        (item_name, basket_ids)
        for item_name, basket_ids in vertical.items()
        if len(basket_ids) >= min_support_count
    ]
    frequent_vertical.sort(key=lambda item: (len(item[1]), item[0]))
    return frequent_vertical, min_support_count


def mine_eclat_frequent_itemsets(
    vertical_items: list[tuple[str, set[str]]],
    *,
    basket_count: int,
    min_support_count: int,
    max_itemset_size: int,
    max_itemsets: int,
) -> tuple[pd.DataFrame, dict[frozenset[str], int], bool]:
    records: list[dict] = []
    support_lookup: dict[frozenset[str], int] = {}
    limit_reached = False

    def store_itemset(itemset: tuple[str, ...], tidset: set[str]) -> bool:
        nonlocal limit_reached

        if len(records) >= max_itemsets:
            limit_reached = True
            return False

        key = frozenset(itemset)
        support_count = len(tidset)
        support_lookup[key] = support_count
        records.append(
            {
                "support": support_count / basket_count if basket_count else 0.0,
                "itemsets": key,
                "support_count": support_count,
            }
        )
        return True

    def recurse(prefix: tuple[str, ...], prefix_tidset: set[str] | None, suffix) -> None:
        nonlocal limit_reached

        for index, (item_name, item_tidset) in enumerate(suffix):
            if limit_reached:
                return

            new_tidset = item_tidset if prefix_tidset is None else prefix_tidset & item_tidset
            if len(new_tidset) < min_support_count:
                continue

            new_itemset = prefix + (item_name,)
            if not store_itemset(new_itemset, new_tidset):
                return

            if len(new_itemset) >= max_itemset_size:
                continue

            next_suffix = []
            for other_item_name, other_tidset in suffix[index + 1 :]:
                intersection = new_tidset & other_tidset
                if len(intersection) >= min_support_count:
                    next_suffix.append((other_item_name, intersection))

            recurse(new_itemset, new_tidset, next_suffix)

    recurse(tuple(), None, vertical_items)
    frequent_itemsets = pd.DataFrame(records, columns=["support", "itemsets", "support_count"])
    return frequent_itemsets, support_lookup, limit_reached


def generate_eclat_rules(
    support_lookup: dict[frozenset[str], int],
    *,
    basket_count: int,
    min_confidence: float,
) -> pd.DataFrame:
    rows: list[dict] = []

    for itemset, support_count in support_lookup.items():
        if len(itemset) < 2:
            continue

        items = tuple(sorted(itemset))
        for antecedent_size in range(1, len(items)):
            for antecedent_tuple in itertools.combinations(items, antecedent_size):
                antecedent = frozenset(antecedent_tuple)
                consequent = itemset - antecedent

                antecedent_count = support_lookup.get(antecedent)
                consequent_count = support_lookup.get(consequent)
                if not antecedent_count or not consequent_count:
                    continue

                confidence = support_count / antecedent_count
                if confidence < min_confidence:
                    continue

                support = support_count / basket_count
                antecedent_support = antecedent_count / basket_count
                consequent_support = consequent_count / basket_count
                lift = confidence / consequent_support if consequent_support else 0.0
                leverage = support - (antecedent_support * consequent_support)
                conviction = (
                    math.inf
                    if math.isclose(confidence, 1.0)
                    else (1 - consequent_support) / (1 - confidence)
                )

                rows.append(
                    {
                        "antecedents": antecedent,
                        "consequents": consequent,
                        "antecedent_count": antecedent_count,
                        "consequent_count": consequent_count,
                        "support_count": support_count,
                        "antecedent support": antecedent_support,
                        "consequent support": consequent_support,
                        "support": support,
                        "confidence": confidence,
                        "lift": lift,
                        "leverage": leverage,
                        "conviction": conviction,
                    }
                )

    if not rows:
        return empty_rules_df()

    return pd.DataFrame(rows).sort_values(
        ["lift", "confidence", "support"],
        ascending=[False, False, False],
    )


def run_eclat_algorithm(
    *,
    basket_items: pd.DataFrame,
    item_level: str,
    min_supports: list[float],
    min_confidences: list[float],
    max_itemset_size: int,
    max_eclat_itemsets: int,
    stats: dict[str, int],
) -> tuple[pd.DataFrame, list[dict]]:
    exported_rules: list[pd.DataFrame] = []
    comparison_rows: list[dict] = []

    for min_support in min_supports:
        support_notes: list[str] = [
            "Frequent itemsets mined once per support threshold and reused "
            "across confidence thresholds."
        ]
        support_lookup: dict[frozenset[str], int] = {}
        frequent_itemset_count = 0
        mining_perf: dict[str, float] = {}
        mining_failed = False

        print(f"ECLAT mining support={min_support}...", flush=True)
        try:
            with measure_performance() as mining_perf:
                vertical_items, min_support_count = build_vertical_itemsets(
                    basket_items,
                    min_support=min_support,
                    basket_count=stats["input_basket_count"],
                )
                support_notes.append(
                    f"Vertical representation built with {len(vertical_items):,} "
                    f"items meeting support count >= {min_support_count:,}."
                )

                frequent_itemsets, support_lookup, limit_reached = mine_eclat_frequent_itemsets(
                    vertical_items,
                    basket_count=stats["input_basket_count"],
                    min_support_count=min_support_count,
                    max_itemset_size=max_itemset_size,
                    max_itemsets=max_eclat_itemsets,
                )
                if limit_reached:
                    support_notes.append(
                        f"Stopped after --max-eclat-itemsets={max_eclat_itemsets:,}; "
                        "rules may be partial for this threshold."
                    )

                frequent_itemset_count = len(frequent_itemsets)
        except Exception as exc:
            support_notes.append(f"FAILED: {exc}")
            mining_failed = True
            frequent_itemset_count = 0

        for min_confidence in min_confidences:
            rules = empty_rules_df()
            rule_perf: dict[str, float] = {}
            notes = support_notes.copy()

            if not mining_failed:
                print(
                    f"ECLAT rules support={min_support} "
                    f"confidence={min_confidence}...",
                    flush=True,
                )
                try:
                    with measure_performance() as rule_perf:
                        rules = generate_eclat_rules(
                            support_lookup,
                            basket_count=stats["input_basket_count"],
                            min_confidence=min_confidence,
                        )
                except Exception as exc:
                    notes.append(f"FAILED: {exc}")

            perf = combine_performance(mining_perf, rule_perf)

            exported_rules.append(
                format_rules_for_export(
                    rules,
                    algorithm_name="ECLAT",
                    item_level=item_level,
                    min_support=min_support,
                    min_confidence=min_confidence,
                )
            )
            comparison_rows.append(
                build_performance_row(
                    algorithm_name="ECLAT",
                    item_level=item_level,
                    min_support=min_support,
                    min_confidence=min_confidence,
                    frequent_itemset_count=frequent_itemset_count,
                    rules_df=rules,
                    perf=perf,
                    input_row_count=stats["input_row_count"],
                    input_basket_count=stats["input_basket_count"],
                    input_item_count=stats["input_item_count"],
                    notes=" | ".join(notes),
                )
            )

            print(
                f"ECLAT support={min_support} confidence={min_confidence}: "
                f"{frequent_itemset_count:,} itemsets, {len(rules):,} rules",
                flush=True,
            )

    rules_df = concat_or_empty(exported_rules, RULE_EXPORT_COLUMNS)
    return rules_df, comparison_rows


def concat_or_empty(frames: list[pd.DataFrame], columns: list[str]) -> pd.DataFrame:
    frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True).loc[:, columns]


def write_csv(df: pd.DataFrame, output_path: Path, columns: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        df = pd.DataFrame(columns=columns)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df):,} rows to {output_path}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Apriori, FP-Growth, and ECLAT association rule mining."
    )
    parser.add_argument(
        "--item-level",
        default="product_category",
        choices=sorted(ITEM_LEVEL_SUFFIXES),
        help="Item level used in the prepared basket CSV.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Prepared basket-item CSV. Defaults to outputs/basket_items_<level>.csv.",
    )
    parser.add_argument(
        "--algorithms",
        default="apriori,fpgrowth,eclat",
        help="Comma-separated algorithms to run: apriori,fpgrowth,eclat.",
    )
    parser.add_argument(
        "--min-supports",
        default="0.001,0.003,0.005,0.01",
        help="Comma-separated support thresholds.",
    )
    parser.add_argument(
        "--min-confidences",
        default="0.3,0.4,0.5,0.6",
        help="Comma-separated confidence thresholds.",
    )
    parser.add_argument(
        "--max-itemset-size",
        type=int,
        default=3,
        help="Maximum itemset size to mine. Increase carefully for large item spaces.",
    )
    parser.add_argument(
        "--max-matrix-items",
        type=int,
        default=10000,
        help=(
            "Deprecated compatibility option. Apriori and FP-Growth now use "
            "pure-Python transaction structures instead of a one-hot matrix."
        ),
    )
    parser.add_argument(
        "--max-eclat-itemsets",
        type=int,
        default=250000,
        help="Safety cap for ECLAT frequent itemsets per threshold combination.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for rule and comparison CSV outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    item_level, _ = normalize_item_level(args.item_level)
    input_path = args.input or default_input_path(args.item_level)
    input_path = input_path if input_path.is_absolute() else PROJECT_ROOT / input_path
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir

    min_supports = parse_float_list(args.min_supports)
    min_confidences = parse_float_list(args.min_confidences)
    algorithms = parse_algorithm_list(args.algorithms)

    print(f"Loading prepared basket dataset: {input_path}", flush=True)
    basket_items = load_prepared_basket_items(input_path)
    stats = input_stats(basket_items)
    print(
        "Input summary: "
        f"{stats['input_row_count']:,} rows, "
        f"{stats['input_basket_count']:,} baskets, "
        f"{stats['input_item_count']:,} items",
        flush=True,
    )
    transactions = build_transactions(basket_items)
    print(f"Built {len(transactions):,} transaction baskets for mining.", flush=True)

    all_comparison_rows: list[dict] = []

    if "apriori" in algorithms:
        apriori_rules, apriori_rows = run_frequent_itemset_algorithm(
            algorithm_name="Apriori",
            miner=mine_apriori_frequent_itemsets,
            transactions=transactions,
            item_level=item_level,
            min_supports=min_supports,
            min_confidences=min_confidences,
            max_itemset_size=args.max_itemset_size,
            stats=stats,
        )
        write_csv(
            apriori_rules,
            output_dir / "association_rules_apriori.csv",
            RULE_EXPORT_COLUMNS,
        )
        all_comparison_rows.extend(apriori_rows)

    if "fpgrowth" in algorithms:
        fpgrowth_rules, fpgrowth_rows = run_frequent_itemset_algorithm(
            algorithm_name="FP-Growth",
            miner=mine_fpgrowth_frequent_itemsets,
            transactions=transactions,
            item_level=item_level,
            min_supports=min_supports,
            min_confidences=min_confidences,
            max_itemset_size=args.max_itemset_size,
            stats=stats,
        )
        write_csv(
            fpgrowth_rules,
            output_dir / "association_rules_fpgrowth.csv",
            RULE_EXPORT_COLUMNS,
        )
        all_comparison_rows.extend(fpgrowth_rows)

    if "eclat" in algorithms:
        eclat_rules, eclat_rows = run_eclat_algorithm(
            basket_items=basket_items,
            item_level=item_level,
            min_supports=min_supports,
            min_confidences=min_confidences,
            max_itemset_size=args.max_itemset_size,
            max_eclat_itemsets=args.max_eclat_itemsets,
            stats=stats,
        )
        write_csv(
            eclat_rules,
            output_dir / "association_rules_eclat.csv",
            RULE_EXPORT_COLUMNS,
        )
        all_comparison_rows.extend(eclat_rows)

    comparison_df = pd.DataFrame(all_comparison_rows, columns=PERFORMANCE_COLUMNS)
    write_csv(
        comparison_df,
        output_dir / "association_rules_comparison.csv",
        PERFORMANCE_COLUMNS,
    )

    print("\nAssociation rule mining complete.", flush=True)


if __name__ == "__main__":
    main()
