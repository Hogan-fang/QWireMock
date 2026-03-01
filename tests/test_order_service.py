from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import qwire_mock.order_service as order_service
from qwire_mock.schemas import OrderResponse, ProductResponse


@pytest.fixture
def order_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(order_service.order_db, "init_db", lambda: None)
    monkeypatch.setattr(order_service, "_status_scheduler", lambda: None)
    order_service._stop_event.clear()
    with TestClient(order_service.app) as client:
        yield client


def _build_order_response(reference: str, status: str = "SUCCESS", fail_reason: str | None = None) -> OrderResponse:
    return OrderResponse(
        reference=reference,
        orderId="PX1001",
        name="Widget Adapter Order",
        orderDate=datetime.now(timezone.utc),
        amount=99.99,
        currency="USD",
        status=status,
        cardNumber="555555******4444",
        products=[ProductResponse(productId="29838-02", count=2, spec="xs-83", status="FAIL" if status == "FAIL" else "PROCESSING")],
        fail_reason=fail_reason,
    )


@pytest.mark.case(point="POST /order creates successfully and returns a masked card")
def test_v2_create_order_success_returns_201_and_masked_card(
    order_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    record_order_keyword,
):
    callback_events: list[tuple[str, str]] = []

    monkeypatch.setattr(order_service.order_db, "exists", lambda _reference: False)
    monkeypatch.setattr(
        order_service.order_db,
        "create_order",
        lambda _request, status, fail_reason=None: _build_order_response(str(_request.reference), status, fail_reason),
    )
    monkeypatch.setattr(order_service.order_db, "get_callback_info", lambda _reference: ("http://localhost:8100/callback", 99.99))
    monkeypatch.setattr(
        order_service,
        "_dispatch_callback",
        lambda order, callback_url, event_type: callback_events.append((str(order.reference), event_type)),
    )

    ref = str(uuid4())
    record_order_keyword(ref)
    payload = {
        "reference": ref,
        "name": "Widget Adapter Order",
        "callback": "http://localhost:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 99.99,
        "currency": "USD",
        "products": [{"productId": "29838-02", "count": 2, "spec": "xs-83"}],
    }

    response = order_client.post("/order", json=payload)
    assert response.status_code == 201
    body = response.json()

    assert body["status"] == "SUCCESS"
    assert body["reference"] == ref
    assert body["cardNumber"] == "555555******4444"
    assert "cvv" not in body
    assert "expiry" not in body
    assert "fail_reason" not in body
    assert callback_events == [(ref, "ORDER_SUCCESS")]


@pytest.mark.case(point="POST /order duplicate reference returns 400 with Order already exists")
def test_v2_create_order_conflict_returns_400(
    order_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    record_order_keyword,
):
    monkeypatch.setattr(order_service.order_db, "exists", lambda _reference: True)

    ref = str(uuid4())
    record_order_keyword(ref)
    payload = {
        "reference": ref,
        "name": "Duplicate Order",
        "callback": "http://localhost:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 10.5,
        "currency": "USD",
        "products": [{"productId": "P-DUP", "count": 1, "spec": "S"}],
    }

    response = order_client.post("/order", json=payload)
    assert response.status_code == 400
    assert response.json() == {"status": "FAIL", "fail_reason": "Order already exists"}


@pytest.mark.case(point="POST /order card number starting with 4 returns 400 and FAIL")
def test_v2_create_order_invalid_card_returns_400(
    order_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    record_order_keyword,
):
    monkeypatch.setattr(order_service.order_db, "exists", lambda _reference: False)
    monkeypatch.setattr(
        order_service.order_db,
        "create_order",
        lambda request, status, fail_reason=None: _build_order_response(
            str(request.reference), status="FAIL", fail_reason="Unsupported card type"
        ),
    )

    ref = str(uuid4())
    record_order_keyword(ref)
    payload = {
        "reference": ref,
        "name": "Invalid Card Order",
        "callback": "http://localhost:8100/callback",
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 99.99,
        "currency": "USD",
        "products": [{"productId": "P1", "count": 1, "spec": "S"}],
    }

    response = order_client.post("/order", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "FAIL"
    assert body["fail_reason"] == "Unsupported card type"


@pytest.mark.case(point="POST /order invalid UUID in request body returns 422 from framework validation")
def test_v2_create_order_invalid_uuid_returns_422(order_client: TestClient, record_order_keyword):
    bad_ref = "1aba8bca-a65b-4954-b459-6757591"
    record_order_keyword(bad_ref)
    payload = {
        "reference": bad_ref,
        "name": "Bad UUID Order",
        "callback": "http://localhost:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 55.0,
        "currency": "USD",
        "products": [{"productId": "P-BAD-UUID", "count": 1, "spec": "S"}],
    }

    response = order_client.post("/order", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()


@pytest.mark.case(point="GET /order invalid UUID returns 400")
def test_v2_get_order_invalid_uuid_returns_400(order_client: TestClient, record_order_keyword):
    record_order_keyword("not-a-uuid")
    response = order_client.get("/order", params={"reference": "not-a-uuid"})
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "FAIL"
    assert body["fail_reason"] == "invalid UUID string"


@pytest.mark.case(point="GET /order order not found returns 404")
def test_v2_get_order_not_found_returns_404(
    order_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    record_order_keyword,
):
    monkeypatch.setattr(order_service.order_db, "get_order", lambda _reference: None)
    ref = str(uuid4())
    record_order_keyword(ref)
    response = order_client.get("/order", params={"reference": ref})
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "FAIL"
    assert body["fail_reason"] == "Order not found"


@pytest.mark.case(point="GET /order successful query returns 200")
def test_v2_get_order_found_returns_200(
    order_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    record_order_keyword,
):
    ref = str(uuid4())
    record_order_keyword(ref)
    monkeypatch.setattr(order_service.order_db, "get_order", lambda _reference: _build_order_response(ref))

    response = order_client.get("/order", params={"reference": ref})
    assert response.status_code == 200
    body = response.json()
    assert body["reference"] == ref
    assert body["status"] == "SUCCESS"
    assert "fail_reason" not in body


@pytest.mark.case(point="Create then query: returns the same reference and orderId")
def test_v2_create_then_get_order_flow(
    order_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    record_order_keyword,
):
    ref = str(uuid4())
    order_response = _build_order_response(ref)

    monkeypatch.setattr(order_service.order_db, "exists", lambda _reference: False)
    monkeypatch.setattr(order_service.order_db, "create_order", lambda _request, status, fail_reason=None: order_response)
    monkeypatch.setattr(order_service.order_db, "get_order", lambda _reference: order_response)
    monkeypatch.setattr(order_service.order_db, "get_callback_info", lambda _reference: None)

    record_order_keyword(ref)

    create_payload = {
        "reference": ref,
        "name": "Create Then Query",
        "callback": "http://localhost:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 31.2,
        "currency": "USD",
        "products": [{"productId": "P-CQ", "count": 1, "spec": "M"}],
    }

    create_response = order_client.post("/order", json=create_payload)
    assert create_response.status_code == 201

    get_response = order_client.get("/order", params={"reference": ref})
    assert get_response.status_code == 200
    assert get_response.json()["reference"] == ref
    assert get_response.json()["orderId"] == order_response.orderId


@pytest.mark.case(point="Amount threshold policy: high amount skips callback, low amount triggers callback")
def test_v2_dispatch_callback_skip_by_amount_policy(monkeypatch: pytest.MonkeyPatch, record_order_keyword):
    called = {"count": 0}

    class DummyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    def _fake_urlopen(*_args, **_kwargs):
        called["count"] += 1
        return DummyResponse()

    monkeypatch.setattr(order_service.urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(order_service, "CALLBACK_SKIP_AMOUNT_GTE", 1000.0)

    high_amount_order = _build_order_response(str(uuid4()))
    high_amount_order.amount = 1200.0
    order_service._dispatch_callback(high_amount_order, "http://localhost:8100/callback", "ORDER_SUCCESS")

    low_amount_order = _build_order_response(str(uuid4()))
    low_amount_order.amount = 99.0
    record_order_keyword(low_amount_order.orderId)
    order_service._dispatch_callback(low_amount_order, "http://localhost:8100/callback", "ORDER_SUCCESS")

    assert called["count"] == 1
