from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
ALGORITHM_DATA_DIR = PROJECT_ROOT / "data_for_algorithm"

NOISE_PATTERNS = (
    "COUPON",
    "MISC SALES",
    "MISCELLANEOUS",
    "FUEL",
)

DEPARTMENT_IMAGES = {
    "PRODUCE": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80",
    "GROCERY": "https://images.unsplash.com/photo-1583258292688-d0213dc5a3a8?auto=format&fit=crop&w=900&q=80",
    "PASTRY": "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=80",
    "MEAT": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=900&q=80",
    "MEAT-PCKGD": "https://images.unsplash.com/photo-1607623814075-e51df1bdc82f?auto=format&fit=crop&w=900&q=80",
    "SEAFOOD": "https://images.unsplash.com/photo-1606755962773-d324e2fb0f45?auto=format&fit=crop&w=900&q=80",
    "SEAFOOD-PCKGD": "https://images.unsplash.com/photo-1606755962773-d324e2fb0f45?auto=format&fit=crop&w=900&q=80",
    "DELI": "https://images.unsplash.com/photo-1551218808-94e220e084d2?auto=format&fit=crop&w=900&q=80",
    "NUTRITION": "https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=900&q=80",
    "DRUG GM": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=900&q=80",
    "COSMETICS": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=900&q=80",
    "FLORAL": "https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=900&q=80",
}

DEFAULT_IMAGE = "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?auto=format&fit=crop&w=900&q=80"

DEPARTMENT_FACTORS = {
    "PRODUCE": 0.85,
    "GROCERY": 1.0,
    "PASTRY": 1.05,
    "DELI": 1.25,
    "NUTRITION": 1.35,
    "DRUG GM": 1.4,
    "COSMETICS": 1.55,
    "MEAT": 1.7,
    "MEAT-PCKGD": 1.55,
    "SEAFOOD": 2.1,
    "SEAFOOD-PCKGD": 1.9,
    "FLORAL": 1.3,
}


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    department: str
    product_type: str
    price: float
    basket_count: int
    basket_share: float
    popularity_rank: int
    image_url: str


@dataclass(frozen=True)
class Rule:
    antecedents: tuple[str, ...]
    consequent: str
    support_count: int
    support: float
    confidence: float
    lift: float


def normalize_item(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip().upper()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def split_itemset(value: object) -> tuple[str, ...]:
    text = normalize_item(value)
    if not text:
        return tuple()
    parts = [normalize_item(part) for part in text.split("|")]
    return tuple(sorted(part for part in parts if part))


def is_catalog_item(name: str, department: str = "") -> bool:
    text = f"{name} {department}".upper()
    return not any(pattern in text for pattern in NOISE_PATTERNS)


def stable_price(name: str, department: str, popularity_rank: int) -> float:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    cents = int(digest[:6], 16) % 1150
    factor = DEPARTMENT_FACTORS.get(department, 1.0)
    popularity_adjustment = max(0, 130 - popularity_rank) / 100
    price = (1.35 + cents / 100 + popularity_adjustment) * factor
    return round(min(max(price, 0.89), 29.95), 2)


def top_value(values: pd.Series, fallback: str) -> str:
    cleaned = values.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    if cleaned.empty:
        return fallback
    return str(cleaned.value_counts().idxmax())


class RecommendationEngine:
    def __init__(
        self,
        basket_path: Path | None = None,
        rules_path: Path | None = None,
        metadata_path: Path | None = None,
    ) -> None:
        self.basket_path = basket_path or OUTPUT_DIR / "basket_items_category.csv"
        self.rules_path = rules_path or self._best_rules_path()
        self.metadata_path = metadata_path or ALGORITHM_DATA_DIR / "basket_items_for_mba.csv"

    def _best_rules_path(self) -> Path:
        for filename in (
            "association_rules_fpgrowth.csv",
            "association_rules_apriori.csv",
            "association_rules_eclat.csv",
        ):
            candidate = OUTPUT_DIR / filename
            if candidate.exists():
                return candidate
        return OUTPUT_DIR / "association_rules_apriori.csv"

    @cached_property
    def basket_df(self) -> pd.DataFrame:
        if not self.basket_path.exists():
            raise FileNotFoundError(
                f"Missing prepared basket file: {self.basket_path}. "
                "Run the association-rule preparation first."
            )

        df = pd.read_csv(
            self.basket_path,
            usecols=["basket_id", "item_name"],
            dtype={"basket_id": "string", "item_name": "string"},
        )
        df["basket_id"] = df["basket_id"].astype("string").str.strip()
        df["item_name"] = df["item_name"].map(normalize_item)
        df = df[(df["basket_id"] != "") & (df["item_name"] != "")]
        df = df.drop_duplicates(["basket_id", "item_name"])
        return df.reset_index(drop=True)

    @cached_property
    def item_counts(self) -> Counter[str]:
        return Counter(self.basket_df["item_name"].tolist())

    @cached_property
    def basket_to_items(self) -> dict[str, tuple[str, ...]]:
        grouped = self.basket_df.groupby("basket_id", sort=False)["item_name"]
        return {
            str(basket_id): tuple(sorted(set(items)))
            for basket_id, items in grouped
        }

    @cached_property
    def item_to_baskets(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        for basket_id, item_name in self.basket_df[["basket_id", "item_name"]].itertuples(index=False):
            mapping.setdefault(str(item_name), set()).add(str(basket_id))
        return mapping

    @cached_property
    def metadata(self) -> dict[str, dict[str, str]]:
        if not self.metadata_path.exists():
            return {}

        df = pd.read_csv(
            self.metadata_path,
            usecols=["department", "product_category", "product_type"],
            dtype="string",
        )
        df["product_category"] = df["product_category"].map(normalize_item)
        df["department"] = df["department"].map(normalize_item)
        df["product_type"] = df["product_type"].map(normalize_item)
        df = df[df["product_category"] != ""]

        metadata: dict[str, dict[str, str]] = {}
        for category, group in df.groupby("product_category", sort=False):
            department = top_value(group["department"], "GROCERY")
            product_type = top_value(group["product_type"], category)
            metadata[str(category)] = {
                "department": department,
                "product_type": product_type,
            }
        return metadata

    @cached_property
    def catalog(self) -> list[CatalogItem]:
        total_baskets = max(1, self.basket_count)
        sorted_items = sorted(self.item_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        used_ids: set[str] = set()
        catalog: list[CatalogItem] = []

        for rank, (name, count) in enumerate(sorted_items, start=1):
            item_meta = self.metadata.get(name, {})
            department = item_meta.get("department", "GROCERY")
            if not is_catalog_item(name, department):
                continue

            base_id = slugify(name)
            item_id = base_id
            suffix = 2
            while item_id in used_ids:
                item_id = f"{base_id}-{suffix}"
                suffix += 1
            used_ids.add(item_id)

            catalog.append(
                CatalogItem(
                    id=item_id,
                    name=name,
                    department=department,
                    product_type=item_meta.get("product_type", name),
                    price=stable_price(name, department, rank),
                    basket_count=int(count),
                    basket_share=round(count / total_baskets, 5),
                    popularity_rank=rank,
                    image_url=DEPARTMENT_IMAGES.get(department, DEFAULT_IMAGE),
                )
            )

        return catalog

    @cached_property
    def catalog_by_name(self) -> dict[str, CatalogItem]:
        return {item.name: item for item in self.catalog}

    @cached_property
    def catalog_by_id(self) -> dict[str, CatalogItem]:
        return {item.id: item for item in self.catalog}

    @cached_property
    def catalog_names(self) -> set[str]:
        return set(self.catalog_by_name)

    @cached_property
    def basket_count(self) -> int:
        return int(self.basket_df["basket_id"].nunique())

    @cached_property
    def rules(self) -> list[Rule]:
        if not self.rules_path.exists():
            return []

        usecols = [
            "antecedents",
            "consequents",
            "support_count",
            "support",
            "confidence",
            "lift",
        ]
        best_rules: dict[tuple[tuple[str, ...], str], Rule] = {}

        for chunk in pd.read_csv(self.rules_path, usecols=usecols, chunksize=50_000):
            chunk = chunk.dropna(subset=["antecedents", "consequents"])
            for row in chunk.itertuples(index=False):
                antecedents = tuple(item for item in split_itemset(row.antecedents) if item in self.catalog_names)
                consequents = tuple(item for item in split_itemset(row.consequents) if item in self.catalog_names)
                if not antecedents or not consequents:
                    continue

                support_count = int(getattr(row, "support_count", 0) or 0)
                support = float(getattr(row, "support", 0) or 0)
                confidence = float(getattr(row, "confidence", 0) or 0)
                lift = float(getattr(row, "lift", 0) or 0)

                for consequent in consequents:
                    if consequent in antecedents:
                        continue
                    candidate = Rule(
                        antecedents=antecedents,
                        consequent=consequent,
                        support_count=support_count,
                        support=support,
                        confidence=confidence,
                        lift=lift,
                    )
                    key = (antecedents, consequent)
                    current = best_rules.get(key)
                    if current is None or self._rule_quality(candidate) > self._rule_quality(current):
                        best_rules[key] = candidate

        return sorted(
            best_rules.values(),
            key=lambda rule: (
                -len(rule.antecedents),
                -rule.support_count,
                -rule.confidence,
                -rule.lift,
                rule.consequent,
            ),
        )

    def _rule_quality(self, rule: Rule) -> tuple[int, float, float, float]:
        return (rule.support_count, rule.confidence, rule.lift, rule.support)

    def normalize_selection(self, raw_items: Iterable[str]) -> list[str]:
        selected: list[str] = []
        for raw in raw_items:
            value = str(raw).strip()
            item = self.catalog_by_id.get(value)
            name = item.name if item else normalize_item(value)
            if name in self.catalog_by_name and name not in selected:
                selected.append(name)
        return selected

    def catalog_items(
        self,
        *,
        search: str = "",
        department: str = "",
        limit: int = 80,
    ) -> list[dict]:
        search_text = normalize_item(search)
        department_text = normalize_item(department)
        if department_text == "ALL":
            department_text = ""

        items = []
        for item in self.catalog:
            if search_text and search_text not in item.name and search_text not in item.product_type:
                continue
            if department_text and item.department != department_text:
                continue
            items.append(asdict(item))
            if len(items) >= limit:
                break
        return items

    def departments(self) -> list[dict]:
        counts = Counter(item.department for item in self.catalog)
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ]

    def recommendations(self, raw_items: Iterable[str], limit: int = 8) -> dict:
        selected = self.normalize_selection(raw_items)
        if not selected:
            return {
                "selected": [],
                "recommendations": [self._popular_payload(item, "Popular basket item") for item in self.catalog[:limit]],
                "match_count": 0,
                "fallback_used": False,
            }

        scored: dict[str, dict] = {}
        selected_set = set(selected)

        for rule in self.rules:
            antecedent_set = set(rule.antecedents)
            if not antecedent_set.issubset(selected_set):
                continue
            if rule.consequent in selected_set:
                continue

            coverage = len(antecedent_set) / max(1, len(selected_set))
            exact_bonus = 18_000 if antecedent_set == selected_set else 0
            score = (
                rule.support_count
                + rule.confidence * 1200
                + min(rule.lift, 30) * 85
                + coverage * 300
                + exact_bonus
            )
            reason = f"Bought with {', '.join(rule.antecedents)}"
            payload = self._recommendation_payload(
                rule.consequent,
                score=score,
                reason=reason,
                support_count=rule.support_count,
                confidence=rule.confidence,
                lift=rule.lift,
                source="association_rule",
            )
            self._store_best_score(scored, payload)

        fallback_used = False
        if len(scored) < limit:
            fallback_used = True
            for payload in self._cooccurrence_recommendations(selected, limit=limit * 2):
                self._store_best_score(scored, payload)

        recommendations = sorted(
            scored.values(),
            key=lambda item: (-item["score"], -item["support_count"], item["name"]),
        )[:limit]

        return {
            "selected": [asdict(self.catalog_by_name[name]) for name in selected],
            "recommendations": recommendations,
            "match_count": len(recommendations),
            "fallback_used": fallback_used,
        }

    def _store_best_score(self, scored: dict[str, dict], payload: dict) -> None:
        current = scored.get(payload["id"])
        if current is None or payload["score"] > current["score"]:
            scored[payload["id"]] = payload

    def _cooccurrence_recommendations(self, selected: list[str], limit: int) -> list[dict]:
        basket_sets = [self.item_to_baskets.get(name, set()) for name in selected]
        if not basket_sets or any(not baskets for baskets in basket_sets):
            return []

        shared_baskets = set.intersection(*basket_sets)
        if not shared_baskets:
            return []

        selected_set = set(selected)
        counts: Counter[str] = Counter()
        for basket_id in shared_baskets:
            for item_name in self.basket_to_items.get(basket_id, tuple()):
                if item_name not in selected_set and item_name in self.catalog_by_name:
                    counts[item_name] += 1

        payloads: list[dict] = []
        for name, count in counts.most_common(limit):
            confidence = count / max(1, len(shared_baskets))
            popularity = self.item_counts.get(name, 1) / max(1, self.basket_count)
            lift = confidence / popularity if popularity else 0
            score = count * 1.35 + confidence * 800 + min(lift, 20) * 55
            payloads.append(
                self._recommendation_payload(
                    name,
                    score=score,
                    reason=f"Appears in {count:,} matching baskets",
                    support_count=int(count),
                    confidence=confidence,
                    lift=lift,
                    source="basket_cooccurrence",
                )
            )
        return payloads

    def _popular_payload(self, item: CatalogItem, reason: str) -> dict:
        return {
            **asdict(item),
            "score": item.basket_count,
            "support_count": item.basket_count,
            "confidence": 0,
            "lift": 0,
            "reason": reason,
            "source": "popular",
        }

    def _recommendation_payload(
        self,
        name: str,
        *,
        score: float,
        reason: str,
        support_count: int,
        confidence: float,
        lift: float,
        source: str,
    ) -> dict:
        item = self.catalog_by_name[name]
        return {
            **asdict(item),
            "score": round(float(score), 4),
            "support_count": int(support_count),
            "confidence": round(float(confidence), 4),
            "lift": round(float(lift), 2),
            "reason": reason,
            "source": source,
        }

    def summary(self) -> dict:
        top_item = self.catalog[0] if self.catalog else None
        max_confidence = max((rule.confidence for rule in self.rules), default=0)
        return {
            "basket_count": self.basket_count,
            "catalog_count": len(self.catalog),
            "rule_count": len(self.rules),
            "department_count": len(self.departments()),
            "top_item": top_item.name if top_item else "",
            "top_item_basket_count": top_item.basket_count if top_item else 0,
            "max_confidence": round(max_confidence, 4),
            "rules_file": self.rules_path.name if self.rules_path.exists() else "",
            "basket_file": self.basket_path.name if self.basket_path.exists() else "",
        }
