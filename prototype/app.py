from __future__ import annotations

import os
from functools import lru_cache

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from order_store import OrderStore
from recommendation_engine import RecommendationEngine


app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@lru_cache(maxsize=1)
def engine() -> RecommendationEngine:
    return RecommendationEngine()


@lru_cache(maxsize=1)
def orders() -> OrderStore:
    return OrderStore()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    summary = engine().summary()
    summary["recent_order_count"] = len(orders().list_orders(limit=50))
    return jsonify({"ok": True, "summary": summary})


@app.get("/api/catalog")
def catalog():
    search = request.args.get("search", "")
    department = request.args.get("department", "")
    limit = max(1, min(int(request.args.get("limit", 120)), 500))
    return jsonify(
        {
            "items": engine().catalog_items(
                search=search,
                department=department,
                limit=limit,
            )
        }
    )


@app.get("/api/departments")
def departments():
    return jsonify({"departments": engine().departments()})


@app.post("/api/recommendations")
def recommendations():
    payload = request.get_json(silent=True) or {}
    item_ids = payload.get("items") or []
    limit = max(1, min(int(payload.get("limit") or 8), 20))
    return jsonify(engine().recommendations(item_ids, limit=limit))


@app.get("/api/orders")
def list_orders():
    limit = max(1, min(int(request.args.get("limit", 6)), 25))
    return jsonify({"orders": orders().list_orders(limit=limit)})


@app.post("/api/orders")
def create_order():
    payload = request.get_json(silent=True) or {}
    order = orders().create_order(
        customer=payload.get("customer") or {},
        items=payload.get("items") or [],
        catalog_by_id=engine().catalog_by_id,
    )
    recommendations_payload = engine().recommendations(
        [item["item_id"] for item in order["items"]],
        limit=6,
    )
    return jsonify({"order": order, "recommendations": recommendations_payload})


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    status_code = 500
    message = str(exc) or "Unexpected server error"
    if isinstance(exc, HTTPException):
        status_code = exc.code or 500
        message = exc.description
    elif isinstance(exc, ValueError):
        status_code = 400

    return jsonify({"ok": False, "error": message}), status_code


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="127.0.0.1", port=5000, debug=debug)
