"""SQLite persistence for orders."""

import json
import os
import sqlite3
from uuid import UUID

from qwire_mock.schemas import OrderResponse, ProductResponse

_DB_PATH = os.environ.get("QWIRE_ORDER_DB", "qwire_mock.db")


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(_DB_PATH)


def init_db() -> None:
    """Create orders table if not exists."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                reference TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                name TEXT,
                order_date TEXT,
                products TEXT NOT NULL,
                card_number TEXT,
                cvv TEXT,
                expiry TEXT,
                amount REAL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    _migrate_add_payment_columns()


def _migrate_add_payment_columns() -> None:
    """Add card_number, cvv, expiry, amount if table already existed without them."""
    conn = _get_conn()
    try:
        cursor = conn.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in cursor.fetchall()}
        if "card_number" in columns:
            return
        for col, typ in [("card_number", "TEXT"), ("cvv", "TEXT"), ("expiry", "TEXT"), ("amount", "REAL")]:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def save_order(order: OrderResponse) -> None:
    """Insert or replace one order."""
    products_json = json.dumps([p.model_dump(mode="json") for p in order.products])
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO orders (
                reference, order_id, name, order_date, products,
                card_number, cvv, expiry, amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(order.reference),
                order.orderId or "",
                order.name or "",
                str(order.orderDate) if order.orderDate else "",
                products_json,
                getattr(order, "cardNumber", None) or "",
                order.cvv or "",
                order.expiry or "",
                order.amount if order.amount is not None else 0.0,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_order(reference: UUID) -> OrderResponse | None:
    """Load order by reference. 返回结果不包含卡号."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT reference, order_id, name, order_date, products,
                      card_number, cvv, expiry, amount
               FROM orders WHERE reference = ?""",
            (str(reference),),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    ref, order_id, name, order_date, products_json, _card, cvv, expiry, amount = row
    products_data = json.loads(products_json)
    products = [ProductResponse(**p) for p in products_data]
    return OrderResponse(
        reference=UUID(ref),
        orderId=order_id,
        name=name,
        orderDate=order_date,
        products=products,
        cvv=cvv or None,
        expiry=expiry or None,
        amount=amount if amount is not None else None,
        cardNumber=None,  # 查询结果不返回卡号
    )


def order_exists(reference: UUID) -> bool:
    """Check if an order with this reference exists."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM orders WHERE reference = ? LIMIT 1",
            (str(reference),),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()
