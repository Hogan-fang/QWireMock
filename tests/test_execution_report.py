from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import qwire_mock.callback_service as callback_service


client = TestClient(callback_service.app)


@pytest.mark.case(point="Execution trace sample: record reference and orderId keywords")
def test_generate_v2_execution_report(record_order_keyword):
    reference = str(uuid4())
    record_order_keyword(reference)
    payload = {
        "reference": reference,
        "orderId": "PX9001",
        "name": "Execution Report Sample Order",
        "orderDate": "2026-02-28T10:00:00Z",
        "amount": 88.88,
        "currency": "USD",
        "status": "SUCCESS",
        "cardNumber": "555555******4444",
        "products": [{"productId": "REPORT-01", "count": 1, "spec": "M", "status": "PROCESSING"}],
    }

    post_resp = client.post("/callback", json=payload)
    record_order_keyword("PX9001")

    check_resp = client.get("/check", params={"reference": reference})

    assert post_resp.status_code == 200
    assert check_resp.status_code == 404
