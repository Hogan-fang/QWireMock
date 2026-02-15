"""Order API: create order (POST /order), search order by reference (GET /order)."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query

from qwire_mock.order_db import get_order, init_db, order_exists, save_order
from qwire_mock.schemas import OrderRequest, OrderResponse, ProductRequest, ProductResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Simple Order API",
    version="1.0.0",
    description="Order management API",
    lifespan=lifespan,
)


def _generate_order_id() -> str:
    """Generate orderId (e.g. PX39280930012)."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"PX{ts}"


def _order_request_to_response(req: OrderRequest, order_id: str) -> OrderResponse:
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
    """Add a new order to the system."""
    if order_exists(body.reference):
        raise HTTPException(status_code=409, detail="Order already exists")
    order_id = _generate_order_id()
    order = _order_request_to_response(body, order_id)
    save_order(order)
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
