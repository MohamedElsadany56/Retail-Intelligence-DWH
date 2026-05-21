from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Iterable

import psutil


# Columns written to outputs/association_rules_comparison.csv.
# Recommendation metrics and the final quality score are filled later when
# the rules are evaluated on held-out test baskets.
PERFORMANCE_COLUMNS = [
    "algorithm_name",
    "item_level",
    "min_support",
    "min_confidence",
    "min_lift",
    "frequent_itemset_count",
    "rule_count",
    "avg_support",
    "avg_confidence",
    "avg_lift",
    "max_lift",
    "runtime_seconds",
    "memory_usage_mb",
    "memory_delta_mb",
    "input_row_count",
    "input_basket_count",
    "input_item_count",
    "precision_at_5",
    "recall_at_5",
    "hit_rate_at_5",
    "coverage",
    "final_quality_score",
    "accepted",
    "notes",
]


@contextmanager
def measure_performance():
    """Measure runtime and resident memory for the wrapped block.

    Usage:
        with measure_performance() as perf:
            ... # work ...
        perf["runtime_seconds"], perf["memory_usage_mb"], perf["memory_delta_mb"]
    """
    process = psutil.Process(os.getpid())

    start_memory = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    result: dict[str, float] = {}

    try:
        yield result
    finally:
        end_time = time.perf_counter()
        end_memory = process.memory_info().rss / (1024 * 1024)

        result["runtime_seconds"] = round(end_time - start_time, 4)
        result["memory_usage_mb"] = round(end_memory, 4)
        result["memory_delta_mb"] = round(end_memory - start_memory, 4)


def summarize_rules(rules_df: Any) -> dict[str, float | int]:
    """Compute the rule-quality summary statistics for one threshold combo."""
    if rules_df is None or rules_df.empty:
        return {
            "rule_count": 0,
            "avg_support": 0.0,
            "avg_confidence": 0.0,
            "avg_lift": 0.0,
            "max_lift": 0.0,
        }

    return {
        "rule_count": int(len(rules_df)),
        "avg_support": round(float(rules_df["support"].mean()), 6),
        "avg_confidence": round(float(rules_df["confidence"].mean()), 6),
        "avg_lift": round(float(rules_df["lift"].mean()), 6),
        "max_lift": round(float(rules_df["lift"].max()), 6),
    }


def empty_recommendation_metrics() -> dict[str, float]:
    """Default recommendation metrics for runs where no rules were produced
    or no test baskets were evaluated."""
    return {
        "precision_at_5": 0.0,
        "recall_at_5": 0.0,
        "hit_rate_at_5": 0.0,
        "coverage": 0.0,
    }


def build_performance_row(
    *,
    algorithm_name: str,
    item_level: str,
    min_support: float,
    min_confidence: float,
    min_lift: float,
    frequent_itemset_count: int,
    rules_df: Any,
    perf: dict[str, float],
    input_row_count: int,
    input_basket_count: int,
    input_item_count: int,
    recommendation_metrics: dict[str, float] | None = None,
    final_quality_score: float | None = None,
    accepted: bool | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Assemble a single comparison-table row using the fixed schema above."""
    rule_metrics = summarize_rules(rules_df)
    rec_metrics = recommendation_metrics or empty_recommendation_metrics()

    row = {
        "algorithm_name": algorithm_name,
        "item_level": item_level,
        "min_support": min_support,
        "min_confidence": min_confidence,
        "min_lift": min_lift,
        "frequent_itemset_count": int(frequent_itemset_count),
        **rule_metrics,
        "runtime_seconds": perf.get("runtime_seconds", 0.0),
        "memory_usage_mb": perf.get("memory_usage_mb", 0.0),
        "memory_delta_mb": perf.get("memory_delta_mb", 0.0),
        "input_row_count": int(input_row_count),
        "input_basket_count": int(input_basket_count),
        "input_item_count": int(input_item_count),
        "precision_at_5": round(float(rec_metrics.get("precision_at_5", 0.0)), 6),
        "recall_at_5": round(float(rec_metrics.get("recall_at_5", 0.0)), 6),
        "hit_rate_at_5": round(float(rec_metrics.get("hit_rate_at_5", 0.0)), 6),
        "coverage": round(float(rec_metrics.get("coverage", 0.0)), 6),
        "final_quality_score": (
            round(float(final_quality_score), 6) if final_quality_score is not None else ""
        ),
        "accepted": "" if accepted is None else bool(accepted),
        "notes": notes,
    }

    return {column: row.get(column, "") for column in PERFORMANCE_COLUMNS}


def min_max_normalize(values: Iterable[float]) -> list[float]:
    """Min-max scale values to [0, 1]. Constant input maps to all zeros so
    that the final score does not silently double-count a metric that has
    no variation across runs."""
    numeric = [float(value) for value in values]
    if not numeric:
        return []
    min_value = min(numeric)
    max_value = max(numeric)
    spread = max_value - min_value
    if spread == 0:
        return [0.0 for _ in numeric]
    return [(value - min_value) / spread for value in numeric]


def compute_final_quality_scores(
    comparison_rows: list[dict[str, Any]],
    *,
    lift_weight: float = 0.35,
    confidence_weight: float = 0.25,
    hit_rate_weight: float = 0.25,
    precision_weight: float = 0.15,
) -> list[float]:
    """Combine the four key metrics into a single normalized score per run.

    Mirrors the spec:
        final_quality_score =
            0.35 * normalized_avg_lift
          + 0.25 * normalized_avg_confidence
          + 0.25 * normalized_hit_rate_at_5
          + 0.15 * normalized_precision_at_5
    """
    if not comparison_rows:
        return []

    norm_lift = min_max_normalize(row.get("avg_lift", 0.0) for row in comparison_rows)
    norm_confidence = min_max_normalize(row.get("avg_confidence", 0.0) for row in comparison_rows)
    norm_hit_rate = min_max_normalize(row.get("hit_rate_at_5", 0.0) for row in comparison_rows)
    norm_precision = min_max_normalize(row.get("precision_at_5", 0.0) for row in comparison_rows)

    scores: list[float] = []
    for index in range(len(comparison_rows)):
        score = (
            lift_weight * norm_lift[index]
            + confidence_weight * norm_confidence[index]
            + hit_rate_weight * norm_hit_rate[index]
            + precision_weight * norm_precision[index]
        )
        scores.append(round(score, 6))
    return scores
