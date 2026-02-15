"""Tests for callback and check API."""

from fastapi.testclient import TestClient

from qwire_mock.callback import app

client = TestClient(app)


def test_callback_then_check() -> None:
    payload = {
        "reference": "d290f1ee-6c54-4b01-90e6-d701748f0851",
        "orderId": "PX39280930012",
        "name": "Widget Adapter Order",
        "orderDate": "2024-01-10T10:15:30Z",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 99.99,
        "products": [
            {"productId": "29838-02", "count": 2, "spec": "xs-83", "status": "shipped"},
        ],
    }
    r = client.post("/callback", json=payload)
    assert r.status_code == 200
    assert r.json() == {"message": "OK"}

    r2 = client.get("/check", params={"reference": "d290f1ee-6c54-4b01-90e6-d701748f0851"})
    assert r2.status_code == 200
    assert r2.json()["reference"] == "d290f1ee-6c54-4b01-90e6-d701748f0851"
    assert r2.json()["orderId"] == "PX39280930012"
    assert len(r2.json()["products"]) == 1


def test_check_not_found() -> None:
    r = client.get("/check", params={"reference": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
