import json
import logging
import os
import threading
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from qwire_mock import order_db
from qwire_mock.config import load_config
from qwire_mock.schemas import OrderRequest, OrderResponse

logger = logging.getLogger(__name__)
CONFIG = load_config()
ORDER_CONFIG = CONFIG["order"]
LOGGING_CONFIG = CONFIG["logging"]


def _ensure_file_logger() -> None:
    logger.setLevel(logging.INFO)
    order_log_path = LOGGING_CONFIG["order_log"]
    existing = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
        and os.path.basename(getattr(handler, "baseFilename", "")) == os.path.basename(order_log_path)
    ]
    if existing:
        return

    file_handler = logging.FileHandler(order_log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(file_handler)


_ensure_file_logger()

POLL_INTERVAL_SECONDS = int(ORDER_CONFIG["poll_interval_seconds"])
CALLBACK_SKIP_AMOUNT_GTE = float(ORDER_CONFIG["callback_skip_amount_gte"])
_stop_event = threading.Event()


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _dispatch_callback(order: OrderResponse, callback_url: str, event_type: str) -> None:
    if order.amount >= CALLBACK_SKIP_AMOUNT_GTE:
        logger.info(
            "skip callback by amount policy: reference=%s amount=%s threshold=%s event=%s",
            order.reference,
            order.amount,
            CALLBACK_SKIP_AMOUNT_GTE,
            event_type,
        )
        return

    payload = order.model_dump(mode="json")
    payload["eventType"] = event_type
    logger.info("dispatch callback -> %s\n%s", callback_url, _json(payload))

    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    request = urllib.request.Request(callback_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            logger.info("callback response status=%s", response.status)
            raw_body = response.read().decode("utf-8", errors="replace").strip()
            if raw_body:
                try:
                    response_payload = json.loads(raw_body)
                    logger.info("callback response body:\n%s", _json(response_payload))
                except json.JSONDecodeError:
                    logger.info("callback response body(raw): %s", raw_body)
    except urllib.error.HTTPError as exc:
        logger.warning("callback http error: %s", exc)
    except Exception as exc:
        logger.warning("callback request failed: %s", exc)


def _status_scheduler() -> None:
    while not _stop_event.is_set():
        transitions = order_db.apply_scheduled_transitions()
        for target in transitions:
            order = order_db.get_order(target.reference)
            if order is None:
                continue
            _dispatch_callback(order, target.callback_url, f"ORDER_{target.target_status}")
        _stop_event.wait(POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    order_db.init_db()
    logger.info("order service startup: scheduler poll_interval=%ss", POLL_INTERVAL_SECONDS)
    scheduler = threading.Thread(target=_status_scheduler, daemon=True)
    scheduler.start()
    try:
        yield
    finally:
        _stop_event.set()
        logger.info("order service shutdown")


app = FastAPI(title="QWire Order API v2", version="2.0.0", lifespan=lifespan)


@app.post("/order")
def create_order(body: OrderRequest):
    logger.info("POST /order request:\n%s", _json(body.model_dump(mode="json")))

    if order_db.exists(body.reference):
        return JSONResponse(status_code=400, content={"status": "FAIL", "fail_reason": "Order already exists"})

    if body.cardNumber.strip().startswith("4"):
        failed_order = order_db.create_order(body, status="FAIL", fail_reason="Unsupported card type")
        payload = failed_order.model_dump(mode="json")
        logger.info("POST /order response(400):\n%s", _json(payload))
        return JSONResponse(status_code=400, content=payload)

    order = order_db.create_order(body, status="SUCCESS")
    callback_info = order_db.get_callback_info(body.reference)
    if callback_info is not None:
        callback_url, _ = callback_info
        _dispatch_callback(order, callback_url, "ORDER_SUCCESS")

    payload = order.model_dump(mode="json")
    payload.pop("fail_reason", None)
    logger.info("POST /order response(201):\n%s", _json(payload))
    return JSONResponse(status_code=201, content=payload)


@app.get("/order")
def get_order(reference: str = Query(..., description="Order reference (UUID)")):
    try:
        reference_uuid = UUID(reference)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"status": "FAIL", "fail_reason": "invalid UUID string", "reference": reference},
        )

    order = order_db.get_order(reference_uuid)
    if order is None:
        return JSONResponse(
            status_code=404,
            content={"status": "FAIL", "fail_reason": "Order not found", "reference": reference},
        )

    payload = order.model_dump(mode="json")
    if order.fail_reason is None:
        payload.pop("fail_reason", None)
    logger.info("GET /order response:\n%s", _json(payload))
    return JSONResponse(status_code=200, content=payload)
