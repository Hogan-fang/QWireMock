"""MySQL persistence for orders. DB: qwire, user: qwire.
orders table has auto-increment id; orderId is generated as PX+id; products in order_products subtable.
"""

import logging
import os
from uuid import UUID

import pymysql
from pymysql.cursors import DictCursor

from qwire_mock.schemas import OrderResponse, ProductResponse

_MYSQL_CONFIG = {
    "host": os.environ.get("QWIRE_MYSQL_HOST", "localhost"),
    "port": int(os.environ.get("QWIRE_MYSQL_PORT", "3306")),
    "user": os.environ.get("QWIRE_MYSQL_USER", "qwire"),
    "password": os.environ.get("QWIRE_MYSQL_PASSWORD", "Qwire2026"),
    "database": os.environ.get("QWIRE_MYSQL_DATABASE", "qwire"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}


def _get_conn(use_db: bool = True):
    kwargs = {**_MYSQL_CONFIG}
    if not use_db:
        kwargs.pop("database", None)
    return pymysql.connect(**kwargs)


def init_db() -> None:
    """Create database if not exists, orders table (with auto-increment id) and order_products subtable."""
    db_name = _MYSQL_CONFIG["database"]
    conn = _get_conn(use_db=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()

    conn = _get_conn(use_db=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'orders'"
            )
            orders_exists = cur.fetchone()["n"] > 0
            if orders_exists:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = 'orders' AND column_name = 'id'"
                )
                has_id = cur.fetchone()["n"] > 0
                if not has_id:
                    cur.execute("DROP TABLE IF EXISTS order_products")
                    cur.execute("DROP TABLE orders")
                    orders_exists = False
            if not orders_exists:
                cur.execute(
                    """
                    CREATE TABLE orders (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        reference VARCHAR(36) NOT NULL UNIQUE,
                        order_id VARCHAR(64) UNIQUE COMMENT 'Business order number PX+id',
                        name VARCHAR(255),
                        order_date VARCHAR(64),
                        card_number VARCHAR(64),
                        cvv VARCHAR(16),
                        expiry VARCHAR(16),
                        amount DOUBLE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS order_products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id INT NOT NULL COMMENT 'FK orders.id',
                    product_id VARCHAR(64) NOT NULL,
                    count INT NOT NULL,
                    spec VARCHAR(128),
                    status VARCHAR(64),
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    INDEX idx_order_id (order_id)
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


def save_order(order: OrderResponse) -> str:
    """Insert order and product rows; generate unique orderId = PX+id; return that orderId."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                    reference, name, order_date, card_number, cvv, expiry, amount
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(order.reference),
                    order.name or "",
                    str(order.orderDate) if order.orderDate else "",
                    getattr(order, "cardNumber", None) or "",
                    order.cvv or "",
                    order.expiry or "",
                    float(order.amount) if order.amount is not None else 0.0,
                ),
            )
            pk = cur.lastrowid
            order_id = f"PX{pk}"
            cur.execute("UPDATE orders SET order_id = %s WHERE id = %s", (order_id, pk))
            for p in order.products:
                cur.execute(
                    """
                    INSERT INTO order_products (order_id, product_id, count, spec, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (pk, p.productId, p.count, p.spec or "", p.status or "pending"),
                )
        conn.commit()
        return order_id
    finally:
        conn.close()


def get_order(reference: UUID) -> OrderResponse | None:
    """Load order by reference (with products from subtable). Response does not include card number."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, reference, order_id, name, order_date,
                          card_number, cvv, expiry, amount
                   FROM orders WHERE reference = %s""",
                (str(reference),),
            )
            row = cur.fetchone()
        if not row:
            return None
        pk = row["id"]
        with conn.cursor() as cur:
            cur.execute(
                """SELECT product_id, count, spec, status
                   FROM order_products WHERE order_id = %s ORDER BY id""",
                (pk,),
            )
            product_rows = cur.fetchall()
    finally:
        conn.close()

    products = [
        ProductResponse(
            productId=r["product_id"],
            count=r["count"],
            spec=r["spec"] or "",
            status=r["status"] or None,
        )
        for r in product_rows
    ]
    return OrderResponse(
        reference=UUID(row["reference"]),
        orderId=row["order_id"],
        name=row["name"],
        orderDate=row["order_date"],
        products=products,
        cvv=row["cvv"] or None,
        expiry=row["expiry"] or None,
        amount=float(row["amount"]) if row["amount"] is not None else None,
        cardNumber=None,
    )


def order_exists(reference: UUID) -> bool:
    """Return whether an order with this reference exists."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM orders WHERE reference = %s LIMIT 1", (str(reference),))
            return cur.fetchone() is not None
    finally:
        conn.close()


def update_order_products_status(reference: UUID, status: str) -> None:
    """Update all products for this order to the given status (e.g. shipped / completed)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE order_products op
                INNER JOIN orders o ON op.order_id = o.id
                SET op.status = %s
                WHERE o.reference = %s
                """,
                (status, str(reference)),
            )
        conn.commit()
    finally:
        conn.close()


def run_scheduled_status_updates() -> None:
    """Update product status by created_at: 30s -> shipped, 60s -> completed.
    Must run shipped->completed before pending->shipped so we do not jump pending->completed in one cycle.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # First: shipped -> completed (due at 60s)
            cur.execute(
                """
                UPDATE order_products op
                INNER JOIN orders o ON op.order_id = o.id
                SET op.status = 'completed'
                WHERE o.created_at <= NOW() - INTERVAL 60 SECOND
                  AND op.status = 'shipped'
                """
            )
            completed = cur.rowcount
            # Then: pending -> shipped (due at 30s); same cycle won't turn newly shipped into completed
            cur.execute(
                """
                UPDATE order_products op
                INNER JOIN orders o ON op.order_id = o.id
                SET op.status = 'shipped'
                WHERE o.created_at <= NOW() - INTERVAL 30 SECOND
                  AND op.status = 'pending'
                """
            )
            shipped = cur.rowcount
        conn.commit()
        if shipped or completed:
            logging.getLogger(__name__).debug(
                "Scheduled status: shipped=%s, completed=%s", shipped, completed
            )
    finally:
        conn.close()
