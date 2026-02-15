"""FastAPI app: callback (receive & cache by reference), check (return by reference)."""

import json
import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query

from qwire_mock.schemas import OrderResponse, Received
from qwire_mock.store import order_store

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Callback API",
    version="1.0.0",
    description="Callback receive and check by reference",
)


@app.post("/callback", response_model=Received)
def callback(body: OrderResponse) -> Received:
    """Receive callback from order system; cache by reference."""
    payload = body.model_dump(mode="json")
    logger.info("Callback received:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
    order_store.put(body.reference, body)
    return Received(message="OK")


@app.get("/check", response_model=OrderResponse)
def check(reference: UUID = Query(..., description="Order reference (UUID)")) -> OrderResponse:
    """Return cached order for the given reference."""
    order = order_store.get(reference)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
