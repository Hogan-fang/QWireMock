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


def _mask_card_number(card: str) -> str:
    """Mask card number: keep first 6 and last 4 characters, replace middle with *."""
    if not card:
        return ""
    card = card.strip()
    n = len(card)
    if n >= 10:
        return card[:6] + "*" * (n - 10) + card[-4:]
    if n >= 4:
        return card[:2] + "*" * (n - 4) + card[-2:]
    return "*" * n


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
                        amount DOUBLE,
                        currency VARCHAR(16) DEFAULT 'USD',
                        status VARCHAR(32) DEFAULT 'processing',
                        fail_reason VARCHAR(255) DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            # Migrate: add status column if missing (existing tables from before status was added)
            db_name = _MYSQL_CONFIG["database"]
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = 'orders' AND column_name = 'status'",
                (db_name,),
            )
            row = cur.fetchone()
            has_status = (row.get("n") or row.get("N") or 0) != 0
            if not has_status:
                cur.execute("ALTER TABLE orders ADD COLUMN status VARCHAR(32) DEFAULT 'processing'")
                conn.commit()
            # Migrate: add currency column if missing
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = 'orders' AND column_name = 'currency'",
                (db_name,),
            )
            row_cur = cur.fetchone()
            has_currency = (row_cur.get("n") or row_cur.get("N") or 0) != 0
            if not has_currency:
                cur.execute("ALTER TABLE orders ADD COLUMN currency VARCHAR(16) DEFAULT 'USD'")
                conn.commit()
            # Migrate: add fail_reason column if missing, or rename failreason -> fail_reason
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = 'orders' AND column_name = 'fail_reason'",
                (db_name,),
            )
            row_fr = cur.fetchone()
            has_fail_reason = (row_fr.get("n") or row_fr.get("N") or 0) != 0
            if not has_fail_reason:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = 'orders' AND column_name = 'failreason'",
                    (db_name,),
                )
                row_old = cur.fetchone()
                has_old = (row_old.get("n") or row_old.get("N") or 0) != 0
                if has_old:
                    cur.execute("ALTER TABLE orders CHANGE COLUMN failreason fail_reason VARCHAR(255) DEFAULT NULL")
                else:
                    cur.execute("ALTER TABLE orders ADD COLUMN fail_reason VARCHAR(255) DEFAULT NULL")
                conn.commit()
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


def save_order(
    order: OrderResponse,
    status: str = "processing",
    fail_reason: str | None = None,
) -> str:
    """Insert order and product rows; generate unique orderId = PX+id; return that orderId."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                    reference, name, order_date, card_number, amount, currency, status, fail_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(order.reference),
                    order.name or "",
                    str(order.orderDate) if order.orderDate else "",
                    _mask_card_number(getattr(order, "cardNumber", None) or ""),
                    float(order.amount) if order.amount is not None else 0.0,
                    getattr(order, "currency", None) or "USD",
                    (status or "processing").lower(),
                    fail_reason or None,
                ),
            )
            pk = cur.lastrowid
            order_id = f"PX{pk}"
            cur.execute("UPDATE orders SET order_id = %s WHERE id = %s", (order_id, pk))
            order_status_lower = (status or "processing").lower()
            product_status_default = "fail" if order_status_lower == "fail" else "pending"
            for p in order.products:
                p_status = (
                    "fail"
                    if order_status_lower == "fail"
                    else ((p.status or product_status_default).lower())
                )
                cur.execute(
                    """
                    INSERT INTO order_products (order_id, product_id, count, spec, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (pk, p.productId, p.count, p.spec or "", p_status),
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
                          card_number, amount, currency, status, fail_reason
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

    def _upper(s: str | None) -> str | None:
        return s.upper() if s else None

    products = [
        ProductResponse(
            productId=r["product_id"],
            count=r["count"],
            spec=r["spec"] or "",
            status=_upper(r.get("status")),
        )
        for r in product_rows
    ]
    raw_status = (row.get("status") or "").strip().lower()
    fail_reason_value = (row.get("fail_reason") or None) if raw_status == "fail" else None
    return OrderResponse(
        reference=UUID(row["reference"]),
        orderId=row["order_id"],
        name=row["name"],
        orderDate=row["order_date"],
        products=products,
        amount=float(row["amount"]) if row["amount"] is not None else None,
        currency=row.get("currency") or "USD",
        status=raw_status.upper() if raw_status else None,
        fail_reason=fail_reason_value,
        cardNumber=row.get("card_number") or None,
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
    """Update all products for this order to the given status (e.g. shipped / complete). Stores lowercase."""
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
                ((status or "").lower(), str(reference)),
            )
        conn.commit()
    finally:
        conn.close()


def run_scheduled_status_updates() -> None:
    """Update product status by created_at: 30s -> shipped, 60s -> complete.
    Must run shipped->complete before pending->shipped so we do not jump pending->complete in one cycle.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            # First: shipped -> complete (due at 60s); only for orders in processing
            cur.execute(
                """
                UPDATE order_products op
                INNER JOIN orders o ON op.order_id = o.id
                SET op.status = 'complete'
                WHERE o.status = 'processing'
                  AND o.created_at <= NOW() - INTERVAL 60 SECOND
                  AND op.status = 'shipped'
                """
            )
            complete_count = cur.rowcount
            # Then: pending -> shipped (due at 30s); only for orders in processing
            cur.execute(
                """
                UPDATE order_products op
                INNER JOIN orders o ON op.order_id = o.id
                SET op.status = 'shipped'
                WHERE o.status = 'processing'
                  AND o.created_at <= NOW() - INTERVAL 30 SECOND
                  AND op.status = 'pending'
                """
            )
            shipped = cur.rowcount
            # Set order status to complete when all its products are complete
            cur.execute(
                """
                UPDATE orders o
                SET o.status = 'complete'
                WHERE o.status = 'processing'
                  AND NOT EXISTS (
                    SELECT 1 FROM order_products op
                    WHERE op.order_id = o.id AND op.status != 'complete'
                  )
                """
            )
        conn.commit()
        if shipped or complete_count:
            logging.getLogger(__name__).debug(
                "Scheduled status: shipped=%s, complete=%s", shipped, complete_count
            )
    finally:
        conn.close()
