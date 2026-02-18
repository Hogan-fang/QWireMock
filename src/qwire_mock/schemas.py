"""Pydantic schemas matching callback.yaml API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProductRequest(BaseModel):
    """Product item in order request."""

    productId: str = Field(..., example="29838-02")
    count: int = Field(..., ge=0, le=100, example=2)
    spec: str = Field(..., example="xs-83")


class ProductResponse(BaseModel):
    """Product item in order."""

    productId: str = Field(..., example="29838-02")
    count: int = Field(..., ge=0, le=100, example=2)
    spec: str = Field(..., example="xs-83")
    status: str | None = Field(None, description="Product processing status", example="shipped")


class OrderRequest(BaseModel):
    """Order create request (order_server.yaml)."""

    reference: UUID = Field(..., example="d290f1ee-6c54-4b01-90e6-d701748f0851")
    name: str = Field(..., example="Widget Adapter Order")
    callback: str = Field(..., example="http://www.xxx.com")
    cardNumber: str = Field(..., description="Card number", example="4111111111111111")
    cvv: str = Field(..., description="CVV", example="123")
    expiry: str = Field(..., description="Expiry e.g. MM/YY", example="12/28")
    amount: float = Field(..., description="Amount", example=99.99)
    currency: str = Field(..., description="Currency code e.g. USD, CNY", example="USD")
    products: list[ProductRequest] = Field(..., min_length=1)


class OrderResponse(BaseModel):
    """Order callback/check payload. Response includes masked card number only; no CVV or expiry."""

    reference: UUID = Field(..., example="d290f1ee-6c54-4b01-90e6-d701748f0851")
    orderId: str | None = Field(None, example="PX39280930012")
    name: str | None = Field(None, example="Widget Adapter Order")
    orderDate: datetime | str | None = Field(None, example="2024-01-10T10:15:30Z")
    amount: float | None = Field(None, description="Amount", example=99.99)
    currency: str | None = Field(None, description="Currency code e.g. USD, CNY", example="USD")
    status: str | None = Field(None, description="Order status, uppercase: PROCESSING, FAIL, COMPLETE")
    fail_reason: str | None = Field(None, description="Failure reason when status is FAIL")
    products: list[ProductResponse] = Field(default_factory=list)
    cardNumber: str | None = Field(None, description="Masked card number (first 6 and last 4 visible)", example="555555******4444")


class Received(BaseModel):
    """Response for successful callback."""

    message: str = Field(default="OK", example="OK")
