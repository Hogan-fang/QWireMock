import json
import logging
import os
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from qwire_mock.config import load_config
from qwire_mock.schemas import OrderResponse, Received

logger = logging.getLogger(__name__)
CONFIG = load_config()
LOGGING_CONFIG = CONFIG["logging"]


def _ensure_file_logger() -> None:
    logger.setLevel(logging.INFO)
    callback_log_path = LOGGING_CONFIG["callback_log"]
    existing = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
        and os.path.basename(getattr(handler, "baseFilename", "")) == os.path.basename(callback_log_path)
    ]
    if existing:
        return

    file_handler = logging.FileHandler(callback_log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(file_handler)


_ensure_file_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("callback service startup")
    try:
        yield
    finally:
        logger.info("callback service shutdown")

app = FastAPI(title="QWire Callback API v2", version="2.0.0", lifespan=lifespan)


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Invalid callback payload: %s", exc.errors())
    return JSONResponse(status_code=400, content={"message": "Invalid order payload", "errors": exc.errors()})


@app.post("/callback", response_model=Received)
def callback(body: OrderResponse) -> Received:
    payload = body.model_dump(mode="json")
    logger.info("POST /callback request:\n%s", _json(payload))

    response = Received(message="OK")
    logger.info("POST /callback response:\n%s", _json(response.model_dump(mode="json")))
    return response


@app.get("/check")
def check(reference: UUID = Query(..., description="Order reference (UUID)")):
    logger.info("GET /check reference=%s -> callback records are log-only, no persisted query", reference)
    raise HTTPException(status_code=404, detail="Callback records are log-only and not queryable")
