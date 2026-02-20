"""Pydantic schemas matching callback.yaml API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProductRequest(BaseModel):
    """Product item in order request."""

    productId: str = Field(..., json_schema_extra={"example": "29838-02"})
    count: int = Field(..., ge=0, le=100, json_schema_extra={"example": 2})
    spec: str = Field(..., json_schema_extra={"example": "xs-83"})


class ProductResponse(BaseModel):
    """Product item in order."""

    productId: str = Field(..., json_schema_extra={"example": "29838-02"})
    count: int = Field(..., ge=0, le=100, json_schema_extra={"example": 2})
    spec: str = Field(..., json_schema_extra={"example": "xs-83"})
    status: str | None = Field(None, description="Product processing status", json_schema_extra={"example": "shipped"})


class OrderRequest(BaseModel):
    """Order create request (order_server.yaml)."""

    reference: UUID = Field(..., json_schema_extra={"example": "d290f1ee-6c54-4b01-90e6-d701748f0851"})
    name: str = Field(..., json_schema_extra={"example": "Widget Adapter Order"})
    cardNumber: str = Field(..., description="Card number", json_schema_extra={"example": "4111111111111111"})
    cvv: str = Field(..., description="CVV", json_schema_extra={"example": "123"})
    expiry: str = Field(..., description="Expiry e.g. MM/YY", json_schema_extra={"example": "12/28"})
    amount: float = Field(..., description="Amount", json_schema_extra={"example": 99.99})
    currency: str = Field(..., description="Currency code e.g. USD, CNY", json_schema_extra={"example": "USD"})
    callback: str = Field(..., json_schema_extra={"example": "http://www.xxx.com"})
    products: list[ProductRequest] = Field(..., min_length=1)


class OrderResponse(BaseModel):
    """Order callback/check payload. Response includes masked card number only; no CVV or expiry."""

    reference: UUID = Field(..., json_schema_extra={"example": "d290f1ee-6c54-4b01-90e6-d701748f0851"})
    orderId: str | None = Field(None, json_schema_extra={"example": "PX39280930012"})
    name: str | None = Field(None, json_schema_extra={"example": "Widget Adapter Order"})
    orderDate: datetime | str | None = Field(None, json_schema_extra={"example": "2024-01-10T10:15:30Z"})
    amount: float | None = Field(None, description="Amount", json_schema_extra={"example": 99.99})
    currency: str | None = Field(None, description="Currency code e.g. USD, CNY", json_schema_extra={"example": "USD"})
    cardNumber: str | None = Field(None, description="Masked card number (first 6 and last 4 visible)", json_schema_extra={"example": "555555******4444"})
    status: str | None = Field(None, description="Order status, uppercase: PROCESSING, FAIL, COMPLETE")
    fail_reason: str | None = Field(None, description="Failure reason when status is FAIL")
    products: list[ProductResponse] = Field(default_factory=list)
 

class Received(BaseModel):
    """Response for successful callback."""

    message: str = Field(default="OK", json_schema_extra={"example": "OK"})
