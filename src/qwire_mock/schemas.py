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
    cardNumber: str = Field(..., description="卡号", example="4111111111111111")
    cvv: str = Field(..., description="CVV", example="123")
    expiry: str = Field(..., description="有效期，如 MM/YY", example="12/28")
    amount: float = Field(..., description="金额", example=99.99)
    products: list[ProductRequest] = Field(..., min_length=1)


class OrderResponse(BaseModel):
    """Order callback/check payload. 查询结果不包含卡号."""

    reference: UUID = Field(..., example="d290f1ee-6c54-4b01-90e6-d701748f0851")
    orderId: str | None = Field(None, example="PX39280930012")
    name: str | None = Field(None, example="Widget Adapter Order")
    orderDate: datetime | str | None = Field(None, example="2024-01-10T10:15:30Z")
    cvv: str | None = Field(None, description="CVV", example="123")
    expiry: str | None = Field(None, description="有效期", example="12/28")
    amount: float | None = Field(None, description="金额", example=99.99)
    products: list[ProductResponse] = Field(default_factory=list)
    # 仅存储用，序列化时排除，查询结果不返回
    cardNumber: str | None = Field(None, exclude=True)


class Received(BaseModel):
    """Response for successful callback."""

    message: str = Field(default="OK", example="OK")
