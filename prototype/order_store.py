from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from recommendation_engine import CatalogItem


RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"
DEFAULT_DB_PATH = RUNTIME_DIR / "orders.db"


class OrderStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    customer_phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subtotal REAL NOT NULL,
                    delivery_fee REAL NOT NULL,
                    discount REAL NOT NULL,
                    total REAL NOT NULL,
                    item_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    line_total REAL NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                );
                """
            )

    def create_order(
        self,
        *,
        customer: dict,
        items: Iterable[dict],
        catalog_by_id: dict[str, CatalogItem],
    ) -> dict:
        self.init_db()
        clean_items = []
        for raw_item in items:
            item_id = str(raw_item.get("item_id") or raw_item.get("id") or "").strip()
            quantity = int(raw_item.get("quantity") or 0)
            if quantity <= 0:
                continue

            catalog_item = catalog_by_id.get(item_id)
            if catalog_item is None:
                raise ValueError(f"Unknown catalog item: {item_id}")

            quantity = min(quantity, 99)
            line_total = round(catalog_item.price * quantity, 2)
            clean_items.append(
                {
                    "item": catalog_item,
                    "quantity": quantity,
                    "line_total": line_total,
                }
            )

        if not clean_items:
            raise ValueError("Order must contain at least one item.")

        customer_name = str(customer.get("name") or "").strip()
        customer_phone = str(customer.get("phone") or "").strip()
        address = str(customer.get("address") or "").strip()
        if not customer_name or not customer_phone or not address:
            raise ValueError("Customer name, phone, and address are required.")

        subtotal = round(sum(row["line_total"] for row in clean_items), 2)
        item_count = sum(row["quantity"] for row in clean_items)
        delivery_fee = 0.0 if subtotal >= 40 else 3.99
        discount = round(subtotal * 0.05, 2) if item_count >= 6 else 0.0
        total = round(subtotal + delivery_fee - discount, 2)
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO orders (
                    id, customer_name, customer_phone, address, status,
                    subtotal, delivery_fee, discount, total, item_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    customer_name,
                    customer_phone,
                    address,
                    "Completed",
                    subtotal,
                    delivery_fee,
                    discount,
                    total,
                    item_count,
                    created_at,
                ),
            )
            conn.executemany(
                """
                INSERT INTO order_items (
                    order_id, item_id, item_name, department, quantity,
                    unit_price, line_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        order_id,
                        row["item"].id,
                        row["item"].name,
                        row["item"].department,
                        row["quantity"],
                        row["item"].price,
                        row["line_total"],
                    )
                    for row in clean_items
                ],
            )

        return self.get_order(order_id)

    def get_order(self, order_id: str) -> dict:
        self.init_db()
        with self.connect() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if order is None:
                raise ValueError(f"Order not found: {order_id}")
            items = conn.execute(
                """
                SELECT item_id, item_name, department, quantity, unit_price, line_total
                FROM order_items
                WHERE order_id = ?
                ORDER BY id
                """,
                (order_id,),
            ).fetchall()

        payload = dict(order)
        payload["items"] = [dict(item) for item in items]
        return payload

    def list_orders(self, limit: int = 6) -> list[dict]:
        self.init_db()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, customer_name, status, total, item_count, created_at
                FROM orders
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
