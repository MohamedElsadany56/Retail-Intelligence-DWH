from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any

import psutil


PERFORMANCE_COLUMNS = [
    "algorithm_name",
    "item_level",
    "min_support",
    "min_confidence",
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
    "notes",
]


@contextmanager
def measure_performance():
    process = psutil.Process(os.getpid())

    start_memory = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()

    result = {}

    try:
        yield result
    finally:
        end_time = time.perf_counter()
        end_memory = process.memory_info().rss / (1024 * 1024)

        result["runtime_seconds"] = round(end_time - start_time, 4)
        result["memory_usage_mb"] = round(end_memory, 4)
        result["memory_delta_mb"] = round(end_memory - start_memory, 4)


def summarize_rules(rules_df: Any) -> dict[str, float | int]:
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


def build_performance_row(
    *,
    algorithm_name: str,
    item_level: str,
    min_support: float,
    min_confidence: float,
    frequent_itemset_count: int,
    rules_df: Any,
    perf: dict[str, float],
    input_row_count: int,
    input_basket_count: int,
    input_item_count: int,
    notes: str = "",
) -> dict[str, Any]:
    rule_metrics = summarize_rules(rules_df)

    row = {
        "algorithm_name": algorithm_name,
        "item_level": item_level,
        "min_support": min_support,
        "min_confidence": min_confidence,
        "frequent_itemset_count": int(frequent_itemset_count),
        **rule_metrics,
        "runtime_seconds": perf.get("runtime_seconds", 0.0),
        "memory_usage_mb": perf.get("memory_usage_mb", 0.0),
        "memory_delta_mb": perf.get("memory_delta_mb", 0.0),
        "input_row_count": int(input_row_count),
        "input_basket_count": int(input_basket_count),
        "input_item_count": int(input_item_count),
        "notes": notes,
    }

    return {column: row.get(column, "") for column in PERFORMANCE_COLUMNS}
