"""Order API: create order (POST /order), search order by reference (GET /order)."""

import json
import logging
import os
import threading
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
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

# Callback service base URL for notifying on status change (e.g. http://localhost:8000)
CALLBACK_SERVICE_URL = os.environ.get("CALLBACK_SERVICE_URL", "http://localhost:8000").rstrip("/")


def _log_request_packet(route: str, payload: dict) -> None:
    """Log request packet in callback-style pretty JSON format."""
    logger.info("%s request packet:\n%s", route, json.dumps(payload, indent=2, ensure_ascii=False))


def _log_response_packet(route: str, payload: dict) -> None:
    """Log response packet in callback-style pretty JSON format."""
    logger.info("%s response packet:\n%s", route, json.dumps(payload, indent=2, ensure_ascii=False))


def _notify_callback_service(references: list[str]) -> None:
    """POST order payload to callback service for each reference (after status flip to shipped/complete)."""
    for ref in references:
        try:
            order = get_order(UUID(ref))
            if order is None:
                continue
            payload = order.model_dump(mode="json")
            if order.fail_reason is None:
                payload.pop("fail_reason", None)
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{CALLBACK_SERVICE_URL}/callback",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    logger.info("Callback notified for order %s", ref)
                else:
                    logger.warning("Callback returned %s for order %s", resp.status, ref)
        except Exception as e:
            logger.exception("Callback notify failed for %s: %s", ref, e)


def _status_poller_thread() -> None:
    """Background thread: mark orders shipped at 30s and complete at 60s by created_at; notify callback service."""
    while not _stop_poller.is_set():
        try:
            updated_refs = run_scheduled_status_updates()
            if updated_refs:
                _notify_callback_service(updated_refs)
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


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert UUID validation errors to business 400 payloads without FastAPI detail schema."""
    has_reference_uuid_error = any(
        "reference" in [str(loc) for loc in err.get("loc", [])]
        and "uuid" in str(err.get("type", "")).lower()
        for err in exc.errors()
    )
    if not has_reference_uuid_error:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    if request.method == "POST" and request.url.path == "/order":
        try:
            req_payload = await request.json()
        except Exception:
            req_payload = {}

        order_like_payload = req_payload if isinstance(req_payload, dict) else {}
        for key in ("cvv", "expiry"):
            order_like_payload.pop(key, None)
        order_like_payload["status"] = "FAIL"
        order_like_payload["fail_reason"] = "invalid UUID string"
        _log_request_packet("POST /order", req_payload if isinstance(req_payload, dict) else {})
        _log_response_packet("POST /order", order_like_payload)
        return JSONResponse(status_code=400, content=order_like_payload)

    error_payload = {"status": "FAIL", "fail_reason": "invalid UUID string"}
    if request.method == "GET" and request.url.path == "/order":
        _log_request_packet("GET /order", {"reference": request.query_params.get("reference")})
        _log_response_packet("GET /order", error_payload)
    return JSONResponse(status_code=400, content=error_payload)


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
    _log_request_packet("POST /order", body.model_dump(mode="json"))

    if (body.cardNumber or "").strip().startswith("4"):
        if not order_exists(body.reference):
            order = _order_request_to_response(body, order_id=None)
            order_id = save_order(order, status="fail", fail_reason="Invalid card")
            order.orderId = order_id
            order.status = "FAIL"
        order_flat = body.model_dump(mode="json")
        for key in ("cvv", "expiry"):
            order_flat.pop(key, None)
        error_payload = {**order_flat, "status": "FAIL", "fail_reason": "Invalid card"}
        _log_response_packet("POST /order", error_payload)
        return JSONResponse(
            status_code=400,
            content=error_payload,
        )
    if order_exists(body.reference):
        existing = get_order(body.reference)
        order_flat = existing.model_dump(mode="json") if existing else {}
        error_payload = {**order_flat, "status": "FAIL", "fail_reason": "Order already exists"}
        _log_response_packet("POST /order", error_payload)
        return JSONResponse(
            status_code=400,
            content=error_payload,
        )
    order = _order_request_to_response(body, order_id=None)
    order_id = save_order(order, status="processing")
    order.orderId = order_id
    order.status = "PROCESSING"

    payload = order.model_dump(mode="json")
    payload.pop("fail_reason", None)
    _log_response_packet("POST /order", payload)
    return JSONResponse(status_code=201, content=payload)


@app.get("/order", response_model=OrderResponse)
def search_order(
    reference: str = Query(..., description="Order reference (UUID)"),
) -> OrderResponse | JSONResponse:
    """Search order by reference."""
    _log_request_packet("GET /order", {"reference": reference})

    try:
        ref_uuid = UUID(reference)
    except (ValueError, TypeError):
        error_payload = {
            "reference": reference,
            "status": "FAIL",
            "fail_reason": "invalid UUID string",
        }
        _log_response_packet("GET /order", error_payload)
        return JSONResponse(
            status_code=400,
            content=error_payload,
        )
    order = get_order(ref_uuid)
    if order is None:
        error_payload = {
            "reference": reference,
            "status": "FAIL",
            "fail_reason": "Order not found",
        }
        _log_response_packet("GET /order", error_payload)
        return JSONResponse(
            status_code=400,
            content=error_payload,
        )

    payload = order.model_dump(mode="json")
    if order.fail_reason is None:
        payload.pop("fail_reason", None)

    _log_response_packet("GET /order", payload)

    return JSONResponse(content=payload)

