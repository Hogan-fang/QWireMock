"""Tests for order API (create order, search order)."""

import uuid

from fastapi.testclient import TestClient

from qwire_mock.order_service import app

client = TestClient(app)


def test_create_order() -> None:
    ref = str(uuid.uuid4())
    payload = {
        "reference": ref,
        "name": "Widget Adapter Order",
        "callback": "http://www.xxx.com/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 99.99,
        "currency": "USD",
        "products": [
            {"productId": "29838-02", "count": 2, "spec": "xs-83"},
        ],
    }
    r = client.post("/order", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["reference"] == ref
    assert data["name"] == "Widget Adapter Order"
    assert data["orderId"] is not None
    assert data["orderId"].startswith("PX")
    assert data["orderDate"] is not None
    assert len(data["products"]) == 1
    assert data["products"][0]["productId"] == "29838-02"
    assert data["products"][0]["count"] == 2
    assert data["products"][0]["spec"] == "xs-83"
    assert data["products"][0]["status"] == "PENDING"
    assert data["status"] == "PROCESSING"
    assert data["cardNumber"] == "555555******4444"  # Masked (first 6 + last 4)
    assert "cvv" not in data
    assert "expiry" not in data
    assert data["amount"] == 99.99
    assert data["currency"] == "USD"


def test_create_order_then_search() -> None:
    ref = str(uuid.uuid4())
    payload = {
        "reference": ref,
        "name": "Another Order",
        "callback": "http://example.com/cb",
        "cardNumber": "5555555555554444",
        "cvv": "456",
        "expiry": "06/27",
        "amount": 199.0,
        "currency": "EUR",
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
    assert r2.json()["status"] == "PROCESSING"
    assert r2.json()["cardNumber"] == "555555******4444"  # Masked
    assert "cvv" not in r2.json()
    assert "expiry" not in r2.json()
    assert r2.json()["amount"] == 199.0
    assert r2.json()["currency"] == "EUR"


def test_create_order_conflict() -> None:
    ref = str(uuid.uuid4())
    payload = {
        "reference": ref,
        "name": "First",
        "callback": "http://x.com",
        "cardNumber": "5555555555554444",
        "cvv": "789",
        "expiry": "01/30",
        "amount": 50.0,
        "currency": "USD",
        "products": [{"productId": "P1", "count": 1, "spec": "s"}],
    }
    client.post("/order", json=payload)
    r = client.post("/order", json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "FAIL"
    assert data["fail_reason"] == "Order already exists"
    assert "reason" not in data
    assert data["reference"] == ref
    assert data["orderId"] is not None
    assert data["cardNumber"] == "555555******4444"  # Masked in existing order
    assert "cvv" not in data
    assert "expiry" not in data


def test_search_order_invalid_uuid() -> None:
    """Invalid reference (not a valid UUID) returns 400 with status FAIL and fail_reason invalid UUID string."""
    bad_reference = "1aba8bca-a65b-4954-b459-6757591"
    r = client.get("/order", params={"reference": bad_reference})
    assert r.status_code == 400
    data = r.json()
    assert data["reference"] == bad_reference
    assert data["status"] == "FAIL"
    assert data["fail_reason"] == "invalid UUID string"
    assert "reason" not in data
    assert "detail" not in data


def test_search_order_not_found() -> None:
    missing_reference = "00000000-0000-0000-0000-000000000000"
    r = client.get("/order", params={"reference": missing_reference})
    assert r.status_code == 400
    data = r.json()
    assert data["reference"] == missing_reference
    assert data["status"] == "FAIL"
    assert data["fail_reason"] == "Order not found"
    assert "reason" not in data
    assert "detail" not in data


def test_create_order_invalid_card_starts_with_4() -> None:
    """Card number starting with 4 returns 400 with status FAIL and fail_reason Invalid card."""
    ref = str(uuid.uuid4())
    payload = {
        "reference": ref,
        "name": "Invalid Card Order",
        "callback": "http://example.com/cb",
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 99.99,
        "currency": "USD",
        "products": [{"productId": "X1", "count": 1, "spec": "s"}],
    }
    r = client.post("/order", json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "FAIL"
    assert data["fail_reason"] == "Invalid card"
    assert "reason" not in data
    assert data["reference"] == ref
    assert data["cardNumber"] == "4111111111111111"
    assert "cvv" not in data
    assert "expiry" not in data

    # GET the failed order by reference returns fail_reason and status FAIL
    r2 = client.get("/order", params={"reference": ref})
    assert r2.status_code == 200
    assert r2.json()["status"] == "FAIL"
    assert r2.json()["fail_reason"] == "Invalid card"


def test_create_order_invalid_uuid_returns_order_structure() -> None:
    """Invalid UUID in POST /order returns 400 business payload (no FastAPI detail)."""
    payload = {
        "reference": "1aba8bca-a65b-4954-b459-6757591",
        "name": "Bad UUID Order",
        "callback": "http://example.com/cb",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 99.99,
        "currency": "USD",
        "products": [{"productId": "X1", "count": 1, "spec": "s"}],
    }
    r = client.post("/order", json=payload)
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "FAIL"
    assert data["fail_reason"] == "invalid UUID string"
    assert data["reference"] == payload["reference"]
    assert data["name"] == payload["name"]
    assert data["callback"] == payload["callback"]
    assert data["cardNumber"] == payload["cardNumber"]
    assert data["amount"] == payload["amount"]
    assert data["currency"] == payload["currency"]
    assert "products" in data
    assert "cvv" not in data
    assert "expiry" not in data
    assert "detail" not in data


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
