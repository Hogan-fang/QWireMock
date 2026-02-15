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
    run_scheduled_status_updates,
    save_order,
)
from qwire_mock.schemas import OrderRequest, OrderResponse, ProductRequest, ProductResponse

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 10  # Poll by created_at every 10s: 30s -> shipped, 60s -> completed
_stop_poller = threading.Event()


def _status_poller_thread() -> None:
    """Background thread: mark orders shipped at 30s and completed at 60s by created_at."""
    while not _stop_poller.is_set():
        try:
            run_scheduled_status_updates()
        except Exception as e:
            logger.exception("Status poller error: %s", e)
        _stop_poller.wait(POLL_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    poller = threading.Thread(target=_status_poller_thread, daemon=True)
    poller.start()
    yield
    _stop_poller.set()


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
        cardNumber=req.cardNumber,  # Stored only; excluded from response
    )


@app.post("/order", response_model=OrderResponse, status_code=201)
def create_order(body: OrderRequest) -> OrderResponse:
    """Add a new order to the system. orderId is generated from DB auto-increment id (PX+id)."""
    if order_exists(body.reference):
        raise HTTPException(status_code=409, detail="Order already exists")
    order = _order_request_to_response(body, order_id=None)
    order_id = save_order(order)
    order.orderId = order_id
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
