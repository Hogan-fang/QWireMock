from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import qwire_mock.callback_service as callback_service

client = TestClient(callback_service.app)


def _callback_payload(reference: str) -> dict:
    return {
        "reference": reference,
        "orderId": "PX2001",
        "name": "Callback Test Order",
        "orderDate": "2026-02-28T10:00:00Z",
        "amount": 99.99,
        "currency": "USD",
        "status": "SUCCESS",
        "cardNumber": "555555******4444",
        "products": [{"productId": "P1", "count": 1, "spec": "S", "status": "PROCESSING"}],
    }


@pytest.mark.case(point="POST /callback valid payload returns 200 and callback data is logged only")
def test_v2_callback_receive_returns_ok(record_order_keyword):
    ref = str(uuid4())
    record_order_keyword(ref)

    response1 = client.post("/callback", json=_callback_payload(ref))
    response2 = client.post("/callback", json=_callback_payload(ref))

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json() == {"message": "OK"}


@pytest.mark.case(point="GET /check returns 404 because callbacks are log-only")
def test_v2_check_not_found_returns_404(record_order_keyword):
    ref = str(uuid4())
    record_order_keyword(ref)
    response = client.get("/check", params={"reference": ref})
    assert response.status_code == 404
    assert "log-only" in response.json()["detail"]


@pytest.mark.case(point="POST /callback invalid payload returns 400 with error details")
def test_v2_callback_invalid_payload_returns_400(record_order_keyword):
    ref = str(uuid4())
    record_order_keyword(ref)
    payload = _callback_payload(ref)
    payload.pop("status")

    response = client.post("/callback", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["message"] == "Invalid order payload"
    assert "errors" in body
