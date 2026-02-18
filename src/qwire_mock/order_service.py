"""Order API: create order (POST /order), search order by reference (GET /order)."""

import json
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from qwire_mock.order_db import (
    _mask_card_number,
    get_order,
    init_db,
    order_exists,
    run_scheduled_status_updates,
    save_order,
)
from qwire_mock.schemas import OrderRequest, OrderResponse, ProductRequest, ProductResponse

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 10  # Poll by created_at every 10s: 30s -> shipped, 60s -> complete
_stop_poller = threading.Event()


def _status_poller_thread() -> None:
    """Background thread: mark orders shipped at 30s and complete at 60s by created_at."""
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
        ProductResponse(productId=p.productId, count=p.count, spec=p.spec, status="PENDING")
        for p in req.products
    ]
    return OrderResponse(
        reference=req.reference,
        orderId=order_id,
        name=req.name,
        orderDate=order_date,
        products=products,
        amount=req.amount,
        currency=req.currency,
        cardNumber=_mask_card_number(req.cardNumber or ""),
    )


@app.post("/order", response_model=OrderResponse, status_code=201)
def create_order(body: OrderRequest) -> OrderResponse:
    """Add a new order to the system. orderId is generated from DB auto-increment id (PX+id)."""
    if (body.cardNumber or "").strip().startswith("4"):
        if not order_exists(body.reference):
            order = _order_request_to_response(body, order_id=None)
            order_id = save_order(order, status="fail", fail_reason="Invalid card")
            order.orderId = order_id
            order.status = "FAIL"
        order_flat = body.model_dump(mode="json")
        for key in ("cvv", "expiry"):
            order_flat.pop(key, None)
        return JSONResponse(
            status_code=400,
            content={**order_flat, "status": "FAIL", "reason": "Invalid card"},
        )
    if order_exists(body.reference):
        existing = get_order(body.reference)
        order_flat = existing.model_dump(mode="json") if existing else {}
        order_flat["status"] = (order_flat.get("status") or "").upper()
        # Do not overlay status: keep the existing order's real status (e.g. COMPLETE)
        return JSONResponse(
            status_code=400,
            content={**order_flat, "reason": "Order already exists"},
        )
    order = _order_request_to_response(body, order_id=None)
    order_id = save_order(order, status="processing")
    order.orderId = order_id
    order.status = "PROCESSING"
    payload = order.model_dump(mode="json")
    logger.info("Order created:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
    return order


@app.get("/order", response_model=OrderResponse)
def search_order(
    reference: str = Query(..., description="Order reference (UUID)"),
) -> OrderResponse | JSONResponse:
    """Search order by reference."""
    try:
        ref_uuid = UUID(reference)
    except (ValueError, TypeError):
        return JSONResponse(
            status_code=400,
            content={"status": "FAIL", "reason": "invalid UUID string"},
        )
    order = get_order(ref_uuid)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
