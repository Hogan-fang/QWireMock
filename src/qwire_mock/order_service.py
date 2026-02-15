"""Order API: create order (POST /order), search order by reference (GET /order)."""

import json
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query

from qwire_mock.order_db import (
    get_order,
    init_db,
    order_exists,
    save_order,
    update_order_products_status,
)
from qwire_mock.schemas import OrderRequest, OrderResponse, ProductRequest, ProductResponse

logger = logging.getLogger(__name__)

DELAY_SHIPPED_SEC = 30
DELAY_COMPLETED_SEC = 60  # 30s shipped + 再30s completed


def _schedule_status_updates(reference: UUID) -> None:
    """创建订单后：30 秒标记为 shipped，再 30 秒标记为 completed."""

    def run_at(delay: float, status: str) -> None:
        def task() -> None:
            try:
                update_order_products_status(reference, status)
                logger.info("Order %s products status -> %s", reference, status)
            except Exception as e:
                logger.exception("Failed to update order %s to %s: %s", reference, status, e)

        t = threading.Timer(delay, task)
        t.daemon = True
        t.start()

    run_at(DELAY_SHIPPED_SEC, "shipped")
    run_at(DELAY_COMPLETED_SEC, "completed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Simple Order API",
    version="1.0.0",
    description="Order management API",
    lifespan=lifespan,
)


def _order_request_to_response(req: OrderRequest, order_id: str | None = None) -> OrderResponse:
    """Build OrderResponse from OrderRequest with generated orderId and orderDate."""
    order_date = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    products = [
        ProductResponse(productId=p.productId, count=p.count, spec=p.spec, status="pending")
        for p in req.products
    ]
    return OrderResponse(
        reference=req.reference,
        orderId=order_id,
        name=req.name,
        orderDate=order_date,
        products=products,
        cvv=req.cvv,
        expiry=req.expiry,
        amount=req.amount,
        cardNumber=req.cardNumber,  # 仅存储，响应中 exclude 不返回
    )


@app.post("/order", response_model=OrderResponse, status_code=201)
def create_order(body: OrderRequest) -> OrderResponse:
    """Add a new order to the system. orderId 由数据库自增 id 生成（PX+id）."""
    if order_exists(body.reference):
        raise HTTPException(status_code=409, detail="Order already exists")
    order = _order_request_to_response(body, order_id=None)
    order_id = save_order(order)
    order.orderId = order_id
    _schedule_status_updates(body.reference)
    payload = order.model_dump(mode="json")
    logger.info("Order created:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
    return order


@app.get("/order", response_model=OrderResponse)
def search_order(
    reference: UUID = Query(..., description="Order reference (UUID)"),
) -> OrderResponse:
    """Search order by reference."""
    order = get_order(reference)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
