from __future__ import annotations

import argparse
import hashlib
import itertools
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from performance_utils import (
    PERFORMANCE_COLUMNS,
    build_performance_row,
    compute_final_quality_scores,
    empty_recommendation_metrics,
    measure_performance,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

RULE_EXPORT_COLUMNS = [
    "algorithm_name",
    "item_level",
    "min_support",
    "min_confidence",
    "min_lift",
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

# Adaptive threshold search defaults (matches the project spec).
# The grid is ordered from STRICTEST to LOOSEST; the adaptive search
# accepts the first run that produces a useful number of rules.
DEFAULT_THRESHOLD_GRID: list[dict[str, float]] = [
    {"min_support": 0.010, "min_confidence": 0.60, "min_lift": 1.50},
    {"min_support": 0.005, "min_confidence": 0.50, "min_lift": 1.30},
    {"min_support": 0.003, "min_confidence": 0.40, "min_lift": 1.20},
    {"min_support": 0.001, "min_confidence": 0.30, "min_lift": 1.00},
]

DEFAULT_MIN_ACCEPTABLE_RULES = 20
DEFAULT_MAX_ACCEPTABLE_RULES = 5000

# Weights for the recommendation score used at test-time:
#   score = 0.45 * lift + 0.35 * confidence + 0.20 * support
REC_SCORE_WEIGHTS = {"lift": 0.45, "confidence": 0.35, "support": 0.20}
DEFAULT_TOP_K = 5

ITEM_LEVEL_SUFFIXES = {
    "category": ("product_category", "category"),
    "product_category": ("product_category", "category"),
    "type": ("product_type", "type"),
    "product_type": ("product_type", "type"),
    "product": ("product_id", "product_id"),
    "product_id": ("product_id", "product_id"),
}


@dataclass(frozen=True)
class ThresholdCombo:
    """One row in the threshold grid: a (support, confidence, lift) triple."""

    min_support: float
    min_confidence: float
    min_lift: float

    def label(self) -> str:
        return (
            f"support={self.min_support}, "
            f"confidence={self.min_confidence}, "
            f"lift={self.min_lift}"
        )


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


def parse_threshold_grid(raw_value: str | None) -> list[ThresholdCombo]:
    """Parse a 'support:confidence:lift, support:confidence:lift, ...' string.

    Returns the default grid when ``raw_value`` is None or empty.
    """
    if not raw_value:
        return [ThresholdCombo(**combo) for combo in DEFAULT_THRESHOLD_GRID]

    combos: list[ThresholdCombo] = []
    for entry in raw_value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = [part.strip() for part in entry.split(":")]
        if len(parts) != 3:
            raise ValueError(
                f"Bad --threshold-grid entry '{entry}'. "
                "Use 'support:confidence:lift' triples separated by commas."
            )
        combos.append(
            ThresholdCombo(
                min_support=float(parts[0]),
                min_confidence=float(parts[1]),
                min_lift=float(parts[2]),
            )
        )
    if not combos:
        raise ValueError("--threshold-grid must contain at least one triple.")
    return combos


def cartesian_to_grid(
    min_supports: list[float],
    min_confidences: list[float],
    *,
    min_lift: float,
) -> list[ThresholdCombo]:
    """Build a threshold grid from the legacy --min-supports / --min-confidences flags.

    Used when the user explicitly wants the older exhaustive sweep.
    Ordered support-ascending, confidence-ascending for stable output.
    """
    grid: list[ThresholdCombo] = []
    for support in sorted(min_supports):
        for confidence in sorted(min_confidences):
            grid.append(
                ThresholdCombo(
                    min_support=support,
                    min_confidence=confidence,
                    min_lift=min_lift,
                )
            )
    return grid


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
    """Render a frozenset as a deterministic pipe-separated string. Pipe is
    used instead of comma so CSV consumers do not need extra quoting."""
    return " | ".join(sorted(str(item) for item in itemset))


def format_rules_for_export(
    rules: pd.DataFrame,
    *,
    algorithm_name: str,
    item_level: str,
    min_support: float,
    min_confidence: float,
    min_lift: float,
) -> pd.DataFrame:
    if rules.empty:
        return pd.DataFrame(columns=RULE_EXPORT_COLUMNS)

    # Build per-row columns first so the frame has a proper index. If we
    # assigned the scalar metadata columns first to an empty DataFrame, the
    # later Series assignments would expand the frame to the Series index and
    # the scalar columns would become all-NaN. .to_numpy() drops the source
    # index to keep alignment robust against any upstream reindex.
    formatted = pd.DataFrame({
        "antecedents": rules["antecedents"].map(format_itemset).to_numpy(),
        "consequents": rules["consequents"].map(format_itemset).to_numpy(),
        "antecedent_count": (
            rules["antecedent_count"].to_numpy()
            if "antecedent_count" in rules.columns
            else 0
        ),
        "consequent_count": (
            rules["consequent_count"].to_numpy()
            if "consequent_count" in rules.columns
            else 0
        ),
        "support_count": (
            rules["support_count"].to_numpy()
            if "support_count" in rules.columns
            else 0
        ),
        "antecedent_support": rules["antecedent support"].to_numpy(),
        "consequent_support": rules["consequent support"].to_numpy(),
        "support": rules["support"].to_numpy(),
        "confidence": rules["confidence"].to_numpy(),
        "lift": rules["lift"].to_numpy(),
        "leverage": (
            rules["leverage"].to_numpy()
            if "leverage" in rules.columns
            else float("nan")
        ),
        "conviction": (
            rules["conviction"].to_numpy()
            if "conviction" in rules.columns
            else float("nan")
        ),
    })
    # Scalars now broadcast across every row.
    formatted["algorithm_name"] = algorithm_name
    formatted["item_level"] = item_level
    formatted["min_support"] = min_support
    formatted["min_confidence"] = min_confidence
    formatted["min_lift"] = min_lift
    return formatted.loc[:, RULE_EXPORT_COLUMNS]


# ---------------------------------------------------------------------------
# Rule generation from a frequent-itemset support lookup
# ---------------------------------------------------------------------------

def generate_rules_from_supports(
    support_lookup: dict[frozenset[str], int],
    *,
    basket_count: int,
    min_confidence: float,
    min_lift: float = 0.0,
) -> pd.DataFrame:
    """Enumerate rules from frequent itemsets and filter by confidence and lift.

    Itemsets of size 1 are skipped (no rule possible). For each k-itemset we
    enumerate every non-empty proper subset as the antecedent; the consequent
    is the complement inside the same itemset.
    """
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
                if lift < min_lift:
                    continue

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


# ---------------------------------------------------------------------------
# Apriori (pure-Python, candidate generation)
# ---------------------------------------------------------------------------

def generate_apriori_candidates(
    previous_level: set[tuple[str, ...]],
    itemset_size: int,
) -> set[tuple[str, ...]]:
    previous_sorted = sorted(previous_level)
    candidates: set[tuple[str, ...]] = set()

    for left_index, left in enumerate(previous_sorted):
        for right in previous_sorted[left_index + 1:]:
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


# ---------------------------------------------------------------------------
# FP-Growth (pure-Python, conditional FP-trees)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ECLAT (vertical tidset representation)
# ---------------------------------------------------------------------------

def build_vertical_itemsets(
    basket_items: pd.DataFrame,
    *,
    min_support: float,
    basket_count: int,
) -> tuple[list[tuple[str, set[str]]], int]:
    min_count = max(1, math.ceil(min_support * basket_count))

    vertical: dict[str, set[str]] = {}
    for basket_id, item_name in basket_items[["basket_id", "item_name"]].itertuples(index=False):
        vertical.setdefault(str(item_name), set()).add(str(basket_id))

    frequent_vertical = [
        (item_name, basket_ids)
        for item_name, basket_ids in vertical.items()
        if len(basket_ids) >= min_count
    ]
    frequent_vertical.sort(key=lambda item: (len(item[1]), item[0]))
    return frequent_vertical, min_count


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
            for other_item_name, other_tidset in suffix[index + 1:]:
                intersection = new_tidset & other_tidset
                if len(intersection) >= min_support_count:
                    next_suffix.append((other_item_name, intersection))

            recurse(new_itemset, new_tidset, next_suffix)

    recurse(tuple(), None, vertical_items)
    frequent_itemsets = pd.DataFrame(records, columns=["support", "itemsets", "support_count"])
    return frequent_itemsets, support_lookup, limit_reached


# ---------------------------------------------------------------------------
# Recommendation testing on held-out baskets
# ---------------------------------------------------------------------------

def parse_rule_itemset(formatted: str) -> frozenset[str]:
    """Inverse of format_itemset: read 'a | b | c' back into a frozenset."""
    if not isinstance(formatted, str) or not formatted:
        return frozenset()
    return frozenset(part.strip() for part in formatted.split(" | ") if part.strip())


def build_test_baskets(
    test_basket_items: pd.DataFrame,
    *,
    min_items: int = 2,
) -> dict[str, list[str]]:
    """Group the test CSV by basket_id and keep baskets with enough items.

    Items are sorted to keep the input/hidden split reproducible regardless
    of original row order in the CSV.
    """
    grouped = (
        test_basket_items.groupby("basket_id", sort=False)["item_name"]
        .apply(lambda values: sorted({str(value) for value in values}))
    )
    return {
        str(basket_id): items
        for basket_id, items in grouped.items()
        if len(items) >= min_items
    }


def split_basket_items(
    basket_id: str,
    items: list[str],
    *,
    random_state: int,
) -> tuple[list[str], list[str]]:
    """Deterministically split one basket's items into (input, hidden) halves.

    We sort items, then derive a hash per item so the resulting order is
    stable across runs but still varies between baskets. The first half of
    that ordering becomes the input (visible to the recommender) and the
    second half becomes the hidden ground-truth set.
    """
    if len(items) < 2:
        return list(items), []

    seed_bytes = str(random_state).encode("utf-8")
    basket_bytes = str(basket_id).encode("utf-8")

    def item_key(item: str) -> str:
        return hashlib.md5(seed_bytes + basket_bytes + item.encode("utf-8")).hexdigest()

    shuffled = sorted(items, key=item_key)
    cutoff = max(1, len(shuffled) // 2)
    input_items = shuffled[:cutoff]
    hidden_items = shuffled[cutoff:]
    return input_items, hidden_items


def prepare_rules_for_scoring(rules_df: pd.DataFrame) -> list[dict]:
    """Convert exported rule rows into a lightweight scoring list.

    Each entry holds the parsed antecedent / consequent sets along with the
    support, confidence, and lift used by the recommendation score.
    """
    if rules_df is None or rules_df.empty:
        return []

    prepared: list[dict] = []
    for record in rules_df.to_dict(orient="records"):
        antecedents = parse_rule_itemset(record.get("antecedents", ""))
        consequents = parse_rule_itemset(record.get("consequents", ""))
        if not antecedents or not consequents:
            continue
        prepared.append(
            {
                "antecedents": antecedents,
                "consequents": consequents,
                "support": float(record.get("support", 0.0) or 0.0),
                "confidence": float(record.get("confidence", 0.0) or 0.0),
                "lift": float(record.get("lift", 0.0) or 0.0),
            }
        )
    return prepared


def recommend_for_basket(
    input_items: set[str],
    prepared_rules: list[dict],
    *,
    top_k: int,
) -> list[str]:
    """Return the top-k recommended items for an input basket.

    A rule fires when its antecedent set is a subset of the visible input.
    Each consequent item earns the rule's recommendation score:
        score = 0.45 * lift + 0.35 * confidence + 0.20 * support
    If the same consequent comes from multiple rules, we keep the strongest
    rule's score (max) so high-quality rules are not diluted by noisy ones.
    Items already in the input basket are never recommended.
    """
    if not prepared_rules or not input_items:
        return []

    candidate_scores: dict[str, float] = {}
    weight_lift = REC_SCORE_WEIGHTS["lift"]
    weight_confidence = REC_SCORE_WEIGHTS["confidence"]
    weight_support = REC_SCORE_WEIGHTS["support"]

    for rule in prepared_rules:
        if not rule["antecedents"].issubset(input_items):
            continue

        score = (
            weight_lift * rule["lift"]
            + weight_confidence * rule["confidence"]
            + weight_support * rule["support"]
        )

        for item in rule["consequents"]:
            if item in input_items:
                continue
            existing = candidate_scores.get(item)
            if existing is None or score > existing:
                candidate_scores[item] = score

    if not candidate_scores:
        return []

    ranked = sorted(candidate_scores.items(), key=lambda pair: (-pair[1], pair[0]))
    return [item for item, _ in ranked[:top_k]]


def evaluate_recommendations_on_test(
    rules_df: pd.DataFrame,
    *,
    test_baskets: dict[str, list[str]],
    total_items: int,
    top_k: int = DEFAULT_TOP_K,
    random_state: int = 42,
) -> dict[str, float]:
    """Compute precision@k, recall@k, hit_rate@k, and coverage over test baskets."""
    if not test_baskets or rules_df is None or rules_df.empty:
        return empty_recommendation_metrics()

    prepared_rules = prepare_rules_for_scoring(rules_df)
    if not prepared_rules:
        return empty_recommendation_metrics()

    evaluated_basket_count = 0
    precision_sum = 0.0
    recall_sum = 0.0
    hit_count = 0
    recommended_items: set[str] = set()

    for basket_id, items in test_baskets.items():
        input_items_list, hidden_items_list = split_basket_items(
            basket_id, items, random_state=random_state
        )
        if not hidden_items_list:
            continue

        input_items = set(input_items_list)
        hidden_items = set(hidden_items_list)
        recommendations = recommend_for_basket(input_items, prepared_rules, top_k=top_k)

        evaluated_basket_count += 1
        recommended_items.update(recommendations)

        if not recommendations:
            continue

        hits = set(recommendations) & hidden_items
        precision_sum += len(hits) / len(recommendations)
        recall_sum += len(hits) / len(hidden_items)
        if hits:
            hit_count += 1

    if evaluated_basket_count == 0:
        return empty_recommendation_metrics()

    coverage = (len(recommended_items) / total_items) if total_items > 0 else 0.0

    return {
        "precision_at_5": precision_sum / evaluated_basket_count,
        "recall_at_5": recall_sum / evaluated_basket_count,
        "hit_rate_at_5": hit_count / evaluated_basket_count,
        "coverage": coverage,
    }


# ---------------------------------------------------------------------------
# Adaptive runner: walks the threshold grid, records every combo,
# and marks the first "acceptable" one as the accepted run per algorithm.
# ---------------------------------------------------------------------------

@dataclass
class AlgorithmRunResult:
    """One (algorithm, combo) result captured for the comparison table."""

    algorithm_name: str
    combo: ThresholdCombo
    rules_export: pd.DataFrame
    frequent_itemset_count: int
    perf: dict[str, float]
    notes: list[str]
    recommendation_metrics: dict[str, float]
    rule_count: int


def _accept_index_for_algorithm(
    runs: list[AlgorithmRunResult],
    *,
    min_acceptable: int,
    max_acceptable: int,
) -> int:
    """Pick the index of the accepted run for one algorithm.

    Strategy:
      1. Walk the grid from strict to loose (the natural order in ``runs``).
         Accept the first run inside [min_acceptable, max_acceptable].
      2. If none fits, fall back to whichever run is closest to that band.
      3. If all runs are empty, accept the last one (loosest tried).
    """
    if not runs:
        return -1

    for index, run in enumerate(runs):
        if min_acceptable <= run.rule_count <= max_acceptable:
            return index

    def distance(run: AlgorithmRunResult) -> int:
        if run.rule_count < min_acceptable:
            return min_acceptable - run.rule_count
        if run.rule_count > max_acceptable:
            return run.rule_count - max_acceptable
        return 0

    if all(run.rule_count == 0 for run in runs):
        return len(runs) - 1

    best_index = 0
    best_distance = distance(runs[0])
    for index in range(1, len(runs)):
        candidate_distance = distance(runs[index])
        if candidate_distance < best_distance:
            best_distance = candidate_distance
            best_index = index
    return best_index


def run_frequent_itemset_algorithm(
    *,
    algorithm_name: str,
    miner,
    transactions: list[tuple[str, ...]],
    item_level: str,
    threshold_grid: list[ThresholdCombo],
    max_itemset_size: int,
    stats: dict[str, int],
    test_baskets: dict[str, list[str]] | None,
    test_total_items: int,
    top_k: int,
    random_state: int,
) -> list[AlgorithmRunResult]:
    """Run one algorithm across the threshold grid and return per-combo results.

    Frequent itemsets are mined ONCE per (algorithm, min_support) pair and
    reused for every confidence/lift threshold that shares the same support.
    """
    results: list[AlgorithmRunResult] = []
    by_support: dict[float, dict] = {}

    for combo in threshold_grid:
        support_cache = by_support.get(combo.min_support)
        notes: list[str] = []

        if support_cache is None:
            cache_notes = [
                "Frequent itemsets mined once per support threshold and "
                "reused across confidence/lift thresholds."
            ]
            mining_failed = False
            support_lookup: dict[frozenset[str], int] = {}
            frequent_itemset_count = 0
            mining_perf: dict[str, float] = {}

            print(
                f"{algorithm_name} mining support={combo.min_support}...",
                flush=True,
            )
            try:
                with measure_performance() as mining_perf:
                    support_lookup, mining_note = miner(
                        transactions,
                        basket_count=stats["input_basket_count"],
                        min_support=combo.min_support,
                        max_itemset_size=max_itemset_size,
                    )
                    cache_notes.append(mining_note)
                    frequent_itemset_count = len(support_lookup)
            except Exception as exc:
                cache_notes.append(f"FAILED: {exc}")
                mining_failed = True

            support_cache = {
                "support_lookup": support_lookup,
                "frequent_itemset_count": frequent_itemset_count,
                "mining_perf": mining_perf,
                "mining_notes": cache_notes,
                "mining_failed": mining_failed,
            }
            by_support[combo.min_support] = support_cache

        notes.extend(support_cache["mining_notes"])
        rules = empty_rules_df()
        rule_perf: dict[str, float] = {}

        if not support_cache["mining_failed"]:
            print(
                f"{algorithm_name} rules support={combo.min_support} "
                f"confidence={combo.min_confidence} lift={combo.min_lift}...",
                flush=True,
            )
            try:
                with measure_performance() as rule_perf:
                    rules = generate_rules_from_supports(
                        support_cache["support_lookup"],
                        basket_count=stats["input_basket_count"],
                        min_confidence=combo.min_confidence,
                        min_lift=combo.min_lift,
                    )
            except Exception as exc:
                notes.append(f"FAILED: {exc}")

        rules_export = format_rules_for_export(
            rules,
            algorithm_name=algorithm_name,
            item_level=item_level,
            min_support=combo.min_support,
            min_confidence=combo.min_confidence,
            min_lift=combo.min_lift,
        )

        if test_baskets:
            rec_metrics = evaluate_recommendations_on_test(
                rules_export,
                test_baskets=test_baskets,
                total_items=test_total_items,
                top_k=top_k,
                random_state=random_state,
            )
        else:
            rec_metrics = empty_recommendation_metrics()

        combined_perf = combine_performance(support_cache["mining_perf"], rule_perf)

        results.append(
            AlgorithmRunResult(
                algorithm_name=algorithm_name,
                combo=combo,
                rules_export=rules_export,
                frequent_itemset_count=support_cache["frequent_itemset_count"],
                perf=combined_perf,
                notes=notes,
                recommendation_metrics=rec_metrics,
                rule_count=len(rules_export),
            )
        )

        print(
            f"{algorithm_name} {combo.label()}: "
            f"{support_cache['frequent_itemset_count']:,} itemsets, "
            f"{len(rules_export):,} rules, "
            f"hit_rate@{top_k}={rec_metrics['hit_rate_at_5']:.3f}",
            flush=True,
        )

    return results


def run_eclat_algorithm(
    *,
    basket_items: pd.DataFrame,
    item_level: str,
    threshold_grid: list[ThresholdCombo],
    max_itemset_size: int,
    max_eclat_itemsets: int,
    stats: dict[str, int],
    test_baskets: dict[str, list[str]] | None,
    test_total_items: int,
    top_k: int,
    random_state: int,
) -> list[AlgorithmRunResult]:
    results: list[AlgorithmRunResult] = []
    by_support: dict[float, dict] = {}

    for combo in threshold_grid:
        support_cache = by_support.get(combo.min_support)
        notes: list[str] = []

        if support_cache is None:
            cache_notes = [
                "ECLAT frequent itemsets mined once per support threshold "
                "and reused across confidence/lift thresholds."
            ]
            mining_failed = False
            support_lookup: dict[frozenset[str], int] = {}
            frequent_itemset_count = 0
            mining_perf: dict[str, float] = {}

            print(f"ECLAT mining support={combo.min_support}...", flush=True)
            try:
                with measure_performance() as mining_perf:
                    vertical_items, eclat_min_count = build_vertical_itemsets(
                        basket_items,
                        min_support=combo.min_support,
                        basket_count=stats["input_basket_count"],
                    )
                    cache_notes.append(
                        f"Vertical representation built with {len(vertical_items):,} "
                        f"items meeting support count >= {eclat_min_count:,}."
                    )
                    _, support_lookup, limit_reached = mine_eclat_frequent_itemsets(
                        vertical_items,
                        basket_count=stats["input_basket_count"],
                        min_support_count=eclat_min_count,
                        max_itemset_size=max_itemset_size,
                        max_itemsets=max_eclat_itemsets,
                    )
                    if limit_reached:
                        cache_notes.append(
                            f"Stopped after --max-eclat-itemsets={max_eclat_itemsets:,}; "
                            "rules may be partial for this threshold."
                        )
                    frequent_itemset_count = len(support_lookup)
            except Exception as exc:
                cache_notes.append(f"FAILED: {exc}")
                mining_failed = True

            support_cache = {
                "support_lookup": support_lookup,
                "frequent_itemset_count": frequent_itemset_count,
                "mining_perf": mining_perf,
                "mining_notes": cache_notes,
                "mining_failed": mining_failed,
            }
            by_support[combo.min_support] = support_cache

        notes.extend(support_cache["mining_notes"])
        rules = empty_rules_df()
        rule_perf: dict[str, float] = {}

        if not support_cache["mining_failed"]:
            print(
                f"ECLAT rules support={combo.min_support} "
                f"confidence={combo.min_confidence} lift={combo.min_lift}...",
                flush=True,
            )
            try:
                with measure_performance() as rule_perf:
                    rules = generate_rules_from_supports(
                        support_cache["support_lookup"],
                        basket_count=stats["input_basket_count"],
                        min_confidence=combo.min_confidence,
                        min_lift=combo.min_lift,
                    )
            except Exception as exc:
                notes.append(f"FAILED: {exc}")

        rules_export = format_rules_for_export(
            rules,
            algorithm_name="ECLAT",
            item_level=item_level,
            min_support=combo.min_support,
            min_confidence=combo.min_confidence,
            min_lift=combo.min_lift,
        )

        if test_baskets:
            rec_metrics = evaluate_recommendations_on_test(
                rules_export,
                test_baskets=test_baskets,
                total_items=test_total_items,
                top_k=top_k,
                random_state=random_state,
            )
        else:
            rec_metrics = empty_recommendation_metrics()

        combined_perf = combine_performance(support_cache["mining_perf"], rule_perf)

        results.append(
            AlgorithmRunResult(
                algorithm_name="ECLAT",
                combo=combo,
                rules_export=rules_export,
                frequent_itemset_count=support_cache["frequent_itemset_count"],
                perf=combined_perf,
                notes=notes,
                recommendation_metrics=rec_metrics,
                rule_count=len(rules_export),
            )
        )

        print(
            f"ECLAT {combo.label()}: "
            f"{support_cache['frequent_itemset_count']:,} itemsets, "
            f"{len(rules_export):,} rules, "
            f"hit_rate@{top_k}={rec_metrics['hit_rate_at_5']:.3f}",
            flush=True,
        )

    return results


# ---------------------------------------------------------------------------
# Output assembly and persistence
# ---------------------------------------------------------------------------

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


def build_comparison_rows(
    runs_by_algorithm: dict[str, list[AlgorithmRunResult]],
    *,
    item_level: str,
    stats: dict[str, int],
    min_acceptable: int,
    max_acceptable: int,
) -> tuple[list[dict], dict[str, AlgorithmRunResult]]:
    """Flatten per-algorithm run lists into comparison rows and pick the accepted run.

    Two passes:
      1. Build all comparison rows (recommendation metrics already on each run).
      2. Compute final_quality_score across the FULL set, then mark accepted runs.
    """
    # Pick the accepted run inside each algorithm and remember both the
    # per-algorithm (local) index and the position the run will occupy
    # in the flat comparison table (global).
    all_runs: list[AlgorithmRunResult] = []
    accepted_runs: dict[str, AlgorithmRunResult] = {}
    accepted_global_indices: set[int] = set()
    offset = 0
    for algorithm_name, runs in runs_by_algorithm.items():
        local_index = _accept_index_for_algorithm(
            runs,
            min_acceptable=min_acceptable,
            max_acceptable=max_acceptable,
        )
        if local_index >= 0:
            accepted_runs[algorithm_name] = runs[local_index]
            accepted_global_indices.add(offset + local_index)
        all_runs.extend(runs)
        offset += len(runs)

    # First pass: build comparison rows without final_quality_score so the
    # normalization step can see every value in the table.
    interim_rows: list[dict] = []
    for run in all_runs:
        interim_rows.append(
            build_performance_row(
                algorithm_name=run.algorithm_name,
                item_level=item_level,
                min_support=run.combo.min_support,
                min_confidence=run.combo.min_confidence,
                min_lift=run.combo.min_lift,
                frequent_itemset_count=run.frequent_itemset_count,
                rules_df=run.rules_export,
                perf=run.perf,
                input_row_count=stats["input_row_count"],
                input_basket_count=stats["input_basket_count"],
                input_item_count=stats["input_item_count"],
                recommendation_metrics=run.recommendation_metrics,
                final_quality_score=None,
                accepted=None,
                notes=" | ".join(run.notes),
            )
        )

    quality_scores = compute_final_quality_scores(interim_rows)

    enriched_rows: list[dict] = []
    for index, row in enumerate(interim_rows):
        row["final_quality_score"] = quality_scores[index] if quality_scores else 0.0
        row["accepted"] = bool(index in accepted_global_indices)
        enriched_rows.append(row)

    return enriched_rows, accepted_runs


def build_final_accepted_table(
    enriched_rows: list[dict],
) -> pd.DataFrame:
    """One row per algorithm: the accepted threshold combo, sorted by quality."""
    accepted_rows = [dict(row) for row in enriched_rows if row.get("accepted") is True]
    if not accepted_rows:
        return pd.DataFrame(columns=PERFORMANCE_COLUMNS)
    df = pd.DataFrame(accepted_rows, columns=PERFORMANCE_COLUMNS)
    return df.sort_values("final_quality_score", ascending=False).reset_index(drop=True)


def print_acceptance_summary(
    enriched_rows: list[dict],
    accepted_runs: dict[str, AlgorithmRunResult],
    *,
    min_acceptable: int,
    max_acceptable: int,
    top_k: int,
) -> None:
    if not accepted_runs:
        print("\nNo algorithm produced an acceptable rule set.", flush=True)
        return

    print(
        "\nAdaptive threshold acceptance summary "
        f"(target: {min_acceptable:,} - {max_acceptable:,} rules):",
        flush=True,
    )

    accepted_by_algorithm = {
        row["algorithm_name"]: row
        for row in enriched_rows
        if row.get("accepted") is True
    }

    overall_best = max(
        accepted_by_algorithm.values(),
        key=lambda row: row.get("final_quality_score") or 0.0,
    )

    for algorithm_name, run in accepted_runs.items():
        accepted_row = accepted_by_algorithm.get(algorithm_name, {})
        score = accepted_row.get("final_quality_score", 0.0)
        rec = run.recommendation_metrics
        print(
            f"- {algorithm_name}: "
            f"support={run.combo.min_support}, "
            f"confidence={run.combo.min_confidence}, "
            f"lift={run.combo.min_lift}, "
            f"rules={run.rule_count:,}, "
            f"avg_conf={accepted_row.get('avg_confidence', 0.0):.3f}, "
            f"avg_lift={accepted_row.get('avg_lift', 0.0):.3f}, "
            f"max_lift={accepted_row.get('max_lift', 0.0):.3f}, "
            f"runtime={run.perf.get('runtime_seconds', 0.0):.2f}s, "
            f"precision@{top_k}={rec['precision_at_5']:.3f}, "
            f"recall@{top_k}={rec['recall_at_5']:.3f}, "
            f"hit_rate@{top_k}={rec['hit_rate_at_5']:.3f}, "
            f"final_quality_score={score:.4f}"
        )

    print(
        f"\nBest overall algorithm by final_quality_score: "
        f"{overall_best['algorithm_name']} (score={overall_best['final_quality_score']:.4f})",
        flush=True,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Apriori, FP-Growth, and ECLAT association rule mining with "
            "adaptive threshold search and (optional) recommendation evaluation."
        )
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
        help=(
            "Prepared basket-item CSV used for MINING (train baskets when a "
            "test split is supplied). Defaults to outputs/basket_items_<level>.csv."
        ),
    )
    parser.add_argument(
        "--test-input",
        type=Path,
        default=None,
        help=(
            "Optional held-out basket-item CSV used to evaluate recommendation "
            "quality (precision@k, recall@k, hit_rate@k, coverage). When omitted, "
            "those metrics are reported as zero and the final quality score "
            "falls back to rule-quality metrics only."
        ),
    )
    parser.add_argument(
        "--algorithms",
        default="apriori,fpgrowth,eclat",
        help="Comma-separated algorithms to run: apriori,fpgrowth,eclat.",
    )
    parser.add_argument(
        "--threshold-grid",
        default=None,
        help=(
            "Adaptive threshold grid as 'support:confidence:lift' triples, "
            "ordered strictest to loosest. Example: "
            "'0.01:0.6:1.5,0.005:0.5:1.3,0.003:0.4:1.2,0.001:0.3:1.0'. "
            "When omitted (and the legacy --min-supports/--min-confidences flags "
            "are also omitted), the project default grid is used."
        ),
    )
    parser.add_argument(
        "--min-supports",
        default=None,
        help=(
            "Legacy cartesian-product mode: comma-separated support thresholds. "
            "Combined with --min-confidences and --min-lift."
        ),
    )
    parser.add_argument(
        "--min-confidences",
        default=None,
        help=(
            "Legacy cartesian-product mode: comma-separated confidence thresholds. "
            "Requires --min-supports."
        ),
    )
    parser.add_argument(
        "--min-lift",
        type=float,
        default=1.0,
        help=(
            "Lift threshold for the legacy cartesian mode. Ignored when "
            "--threshold-grid is supplied (the grid carries its own lift values)."
        ),
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
        "--min-acceptable-rules",
        type=int,
        default=DEFAULT_MIN_ACCEPTABLE_RULES,
        help="Lower bound of the adaptive acceptance band.",
    )
    parser.add_argument(
        "--max-acceptable-rules",
        type=int,
        default=DEFAULT_MAX_ACCEPTABLE_RULES,
        help="Upper bound of the adaptive acceptance band.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Top-k cutoff used by the recommendation evaluation step.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Seed for the deterministic test-basket input/hidden split.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for rule and comparison CSV outputs.",
    )
    return parser.parse_args()


def resolve_threshold_grid(args: argparse.Namespace) -> tuple[list[ThresholdCombo], str]:
    """Decide between the new adaptive grid and the legacy cartesian mode."""
    if args.threshold_grid:
        return parse_threshold_grid(args.threshold_grid), "explicit threshold grid"

    if args.min_supports or args.min_confidences:
        if not (args.min_supports and args.min_confidences):
            raise SystemExit(
                "Legacy cartesian mode requires both --min-supports and --min-confidences."
            )
        grid = cartesian_to_grid(
            parse_float_list(args.min_supports),
            parse_float_list(args.min_confidences),
            min_lift=args.min_lift,
        )
        return grid, f"legacy cartesian product (min_lift={args.min_lift})"

    return parse_threshold_grid(None), "default adaptive threshold grid"


def main() -> None:
    args = parse_args()
    item_level, _ = normalize_item_level(args.item_level)
    input_path = args.input or default_input_path(args.item_level)
    input_path = input_path if input_path.is_absolute() else PROJECT_ROOT / input_path
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir

    threshold_grid, grid_description = resolve_threshold_grid(args)
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
    print(
        f"Using {grid_description} with {len(threshold_grid)} combo(s); "
        f"acceptance band = [{args.min_acceptable_rules:,}, "
        f"{args.max_acceptable_rules:,}] rules.",
        flush=True,
    )

    test_baskets: dict[str, list[str]] = {}
    test_total_items = 0
    if args.test_input:
        test_input_path = args.test_input
        test_input_path = test_input_path if test_input_path.is_absolute() else PROJECT_ROOT / test_input_path
        print(f"\nLoading test basket dataset: {test_input_path}", flush=True)
        test_basket_items = load_prepared_basket_items(test_input_path)
        test_baskets = build_test_baskets(test_basket_items, min_items=2)
        test_total_items = int(test_basket_items["item_name"].nunique())
        print(
            f"Test summary: {len(test_baskets):,} baskets with >= 2 items, "
            f"{test_total_items:,} unique items.",
            flush=True,
        )
    else:
        print(
            "\nNo --test-input provided; recommendation metrics will be zero "
            "and the final quality score will use only rule-quality metrics.",
            flush=True,
        )

    runs_by_algorithm: dict[str, list[AlgorithmRunResult]] = {}

    if "apriori" in algorithms:
        runs_by_algorithm["Apriori"] = run_frequent_itemset_algorithm(
            algorithm_name="Apriori",
            miner=mine_apriori_frequent_itemsets,
            transactions=transactions,
            item_level=item_level,
            threshold_grid=threshold_grid,
            max_itemset_size=args.max_itemset_size,
            stats=stats,
            test_baskets=test_baskets,
            test_total_items=test_total_items,
            top_k=args.top_k,
            random_state=args.random_state,
        )

    if "fpgrowth" in algorithms:
        runs_by_algorithm["FP-Growth"] = run_frequent_itemset_algorithm(
            algorithm_name="FP-Growth",
            miner=mine_fpgrowth_frequent_itemsets,
            transactions=transactions,
            item_level=item_level,
            threshold_grid=threshold_grid,
            max_itemset_size=args.max_itemset_size,
            stats=stats,
            test_baskets=test_baskets,
            test_total_items=test_total_items,
            top_k=args.top_k,
            random_state=args.random_state,
        )

    if "eclat" in algorithms:
        runs_by_algorithm["ECLAT"] = run_eclat_algorithm(
            basket_items=basket_items,
            item_level=item_level,
            threshold_grid=threshold_grid,
            max_itemset_size=args.max_itemset_size,
            max_eclat_itemsets=args.max_eclat_itemsets,
            stats=stats,
            test_baskets=test_baskets,
            test_total_items=test_total_items,
            top_k=args.top_k,
            random_state=args.random_state,
        )

    # Persist per-algorithm rule CSVs (concatenated across every combo).
    rule_file_names = {
        "Apriori": "association_rules_apriori.csv",
        "FP-Growth": "association_rules_fpgrowth.csv",
        "ECLAT": "association_rules_eclat.csv",
    }
    for algorithm_name, runs in runs_by_algorithm.items():
        rules_df = concat_or_empty(
            [run.rules_export for run in runs],
            RULE_EXPORT_COLUMNS,
        )
        write_csv(
            rules_df,
            output_dir / rule_file_names[algorithm_name],
            RULE_EXPORT_COLUMNS,
        )

    # Build the unified comparison + accepted tables.
    enriched_rows, accepted_runs = build_comparison_rows(
        runs_by_algorithm,
        item_level=item_level,
        stats=stats,
        min_acceptable=args.min_acceptable_rules,
        max_acceptable=args.max_acceptable_rules,
    )
    comparison_df = pd.DataFrame(enriched_rows, columns=PERFORMANCE_COLUMNS)
    write_csv(
        comparison_df,
        output_dir / "association_rules_comparison.csv",
        PERFORMANCE_COLUMNS,
    )

    final_accepted_df = build_final_accepted_table(enriched_rows)
    write_csv(
        final_accepted_df,
        output_dir / "final_accepted_association_metrics.csv",
        PERFORMANCE_COLUMNS,
    )

    print_acceptance_summary(
        enriched_rows,
        accepted_runs,
        min_acceptable=args.min_acceptable_rules,
        max_acceptable=args.max_acceptable_rules,
        top_k=args.top_k,
    )

    print("\nAssociation rule mining complete.", flush=True)


if __name__ == "__main__":
    main()