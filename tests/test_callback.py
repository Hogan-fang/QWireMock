"""Tests for callback and check API."""

import json
import threading
import time
import urllib.error
import urllib.request
import uuid

import pytest

from fastapi.testclient import TestClient

from qwire_mock.callback import app

client = TestClient(app)

# Base URLs when running integration test with live servers
CALLBACK_URL = "http://127.0.0.1:8000"
ORDER_URL = "http://127.0.0.1:9000"
POLL_INTERVAL = 5
SHIPPED_TIMEOUT = 35  # seconds to get shipped callback
COMPLETE_TIMEOUT = 40  # seconds after shipped to get complete callback


def _http_get(url: str, timeout: int = 10) -> tuple[int, dict | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return -1, None


def _http_delete(url: str, timeout: int = 10) -> int:
    try:
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def _http_post(url: str, data: dict, timeout: int = 10) -> tuple[int, dict | None]:
    try:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return -1, None


def test_callback_then_check() -> None:
    """Unit test: POST /callback then GET /check returns cached order."""
    payload = {
        "reference": "d290f1ee-6c54-4b01-90e6-d701748f0851",
        "orderId": "PX39280930012",
        "name": "Widget Adapter Order",
        "orderDate": "2024-01-10T10:15:30Z",
        "amount": 99.99,
        "currency": "USD",
        "products": [
            {"productId": "29838-02", "count": 2, "spec": "xs-83", "status": "SHIPPED"},
        ],
    }
    r = client.post("/callback", json=payload)
    assert r.status_code == 200
    assert r.json() == {"message": "OK"}

    r2 = client.get("/check", params={"reference": "d290f1ee-6c54-4b01-90e6-d701748f0851"})
    assert r2.status_code == 200
    assert r2.json()["reference"] == "d290f1ee-6c54-4b01-90e6-d701748f0851"
    assert r2.json()["orderId"] == "PX39280930012"
    assert "cvv" not in r2.json()
    assert "expiry" not in r2.json()
    assert len(r2.json()["products"]) == 1


def test_check_not_found() -> None:
    r = client.get("/check", params={"reference": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


@pytest.mark.integration
def test_order_create_then_callback_shipped_then_complete() -> None:
    """Integration: create 1 order, poll /check every 5s; within 35s get shipped callback, then get complete."""
    import uvicorn

    def run_callback() -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        server.run()

    def run_order() -> None:
        from qwire_mock.order_service import app as order_app

        config = uvicorn.Config(order_app, host="127.0.0.1", port=9000, log_level="warning")
        server = uvicorn.Server(config)
        server.run()

    t1 = threading.Thread(target=run_callback, daemon=True)
    t2 = threading.Thread(target=run_order, daemon=True)
    t1.start()
    t2.start()
    time.sleep(4)

    try:
        # Clear callback cache
        status = _http_delete(f"{CALLBACK_URL}/clear")
        assert status in (200, 204, -1), f"Clear failed: {status}"

        # Create one order
        ref = str(uuid.uuid4())
        order_payload = {
            "reference": ref,
            "name": "Callback Test Order",
            "callback": f"{CALLBACK_URL}/callback",
            "cardNumber": "5555555555554444",
            "cvv": "123",
            "expiry": "12/28",
            "amount": 99.99,
            "currency": "USD",
            "products": [{"productId": "P1", "count": 1, "spec": "s"}],
        }
        status, create_data = _http_post(f"{ORDER_URL}/order", order_payload)
        assert status == 201, f"Create order failed: {status} {create_data}"
        assert create_data and create_data.get("reference") == ref
        assert create_data.get("status") == "PROCESSING"

        # Phase 1: poll /check every 5s, within 35s expect shipped
        check_url = f"{CALLBACK_URL}/check?reference={ref}"
        shipped_ok = False
        for _ in range(max(1, SHIPPED_TIMEOUT // POLL_INTERVAL)):
            time.sleep(POLL_INTERVAL)
            code, data = _http_get(check_url)
            if code == 200 and data:
                products = data.get("products") or []
                if any((p.get("status") or "").upper() == "SHIPPED" for p in products):
                    shipped_ok = True
                    break
                if data.get("status") == "COMPLETE":
                    shipped_ok = True
                    break
        assert shipped_ok, "Shipped-phase callback not received within 35s"

        # Phase 2: poll for complete; within COMPLETE_TIMEOUT expect status COMPLETE
        complete_ok = False
        for _ in range(max(1, COMPLETE_TIMEOUT // POLL_INTERVAL)):
            time.sleep(POLL_INTERVAL)
            code, data = _http_get(check_url)
            if code == 200 and data and (data.get("status") or "").upper() == "COMPLETE":
                products = data.get("products") or []
                if all((p.get("status") or "").upper() == "COMPLETE" for p in products):
                    complete_ok = True
                    break
        assert complete_ok, "Complete-phase callback not received within timeout"
    finally:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
