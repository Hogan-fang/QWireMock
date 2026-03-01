from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OrderStatus = Literal["SUCCESS", "COMPLETED", "FAIL"]


class ProductRequest(BaseModel):
    productId: str
    count: int = Field(..., ge=0, le=100)
    spec: str


class ProductResponse(BaseModel):
    productId: str
    count: int = Field(..., ge=0, le=100)
    spec: str
    status: str


class OrderRequest(BaseModel):
    reference: UUID
    name: str
    callback: str
    cardNumber: str
    cvv: str
    expiry: str
    amount: float
    currency: str
    products: list[ProductRequest]


class OrderResponse(BaseModel):
    reference: UUID
    orderId: str
    name: str
    orderDate: datetime
    amount: float
    currency: str
    status: OrderStatus
    cardNumber: str
    products: list[ProductResponse]
    fail_reason: str | None = None


class Received(BaseModel):
    message: str = "OK"


class CallbackRecord(BaseModel):
    reference: UUID
    receivedAt: datetime
    payload: OrderResponse


class CallbackCheckResponse(BaseModel):
    reference: UUID
    total: int
    records: list[CallbackRecord]
