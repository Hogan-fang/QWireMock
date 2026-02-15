"""Tests for order API (create order, search order)."""

from fastapi.testclient import TestClient

from qwire_mock.order_service import app

client = TestClient(app)

_REF = "d290f1ee-6c54-4b01-90e6-d701748f0851"
_ORDER_PAYLOAD = {
    "reference": _REF,
    "name": "Widget Adapter Order",
    "callback": "http://www.xxx.com/callback",
    "cardNumber": "4111111111111111",
    "cvv": "123",
    "expiry": "12/28",
    "amount": 99.99,
    "products": [
        {"productId": "29838-02", "count": 2, "spec": "xs-83"},
    ],
}


def test_create_order() -> None:
    r = client.post("/order", json=_ORDER_PAYLOAD)
    assert r.status_code == 201
    data = r.json()
    assert data["reference"] == _REF
    assert data["name"] == "Widget Adapter Order"
    assert data["orderId"] is not None
    assert data["orderId"].startswith("PX")
    assert data["orderDate"] is not None
    assert len(data["products"]) == 1
    assert data["products"][0]["productId"] == "29838-02"
    assert data["products"][0]["count"] == 2
    assert data["products"][0]["spec"] == "xs-83"
    assert data["products"][0]["status"] == "pending"
    assert "cardNumber" not in data  # 查询结果不显示卡号
    assert data["cvv"] == "123"
    assert data["expiry"] == "12/28"
    assert data["amount"] == 99.99


def test_create_order_then_search() -> None:
    payload = {
        "reference": "e390f1ee-6c54-4b01-90e6-d701748f0852",
        "name": "Another Order",
        "callback": "http://example.com/cb",
        "cardNumber": "4242424242424242",
        "cvv": "456",
        "expiry": "06/27",
        "amount": 199.0,
        "products": [{"productId": "A1", "count": 1, "spec": "m"}],
    }
    r1 = client.post("/order", json=payload)
    assert r1.status_code == 201
    ref = r1.json()["reference"]

    r2 = client.get("/order", params={"reference": ref})
    assert r2.status_code == 200
    assert r2.json()["reference"] == ref
    assert r2.json()["name"] == "Another Order"
    assert r2.json()["orderId"] == r1.json()["orderId"]
    assert "cardNumber" not in r2.json()
    assert r2.json()["amount"] == 199.0


def test_create_order_conflict() -> None:
    payload = {
        "reference": "f490f1ee-6c54-4b01-90e6-d701748f0853",
        "name": "First",
        "callback": "http://x.com",
        "cardNumber": "5555555555554444",
        "cvv": "789",
        "expiry": "01/30",
        "amount": 50.0,
        "products": [{"productId": "P1", "count": 1, "spec": "s"}],
    }
    client.post("/order", json=payload)
    r = client.post("/order", json=payload)
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()


def test_search_order_not_found() -> None:
    r = client.get("/order", params={"reference": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
