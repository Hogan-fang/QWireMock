import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import qwire_mock.order_service as order_service
from qwire_mock import order_db


def _maybe_clear_orders() -> None:
    if os.environ.get("QWIRE_V2_CLEAR_DB_BEFORE_TEST", "0") == "1":
        order_db.clear_orders()


@pytest.fixture
def integration_order_client():
    order_db.init_db()
    with TestClient(order_service.app) as client:
        yield client


@pytest.mark.v2_integration
@pytest.mark.case(point="Integration: POST /order persists successfully into v2_orders/v2_order_products")
def test_v2_integration_create_order_persists_db(integration_order_client: TestClient, record_order_keyword):
    _maybe_clear_orders()

    ref = str(uuid4())
    record_order_keyword(ref)

    payload = {
        "reference": ref,
        "name": "Integration Persist Order",
        "callback": "http://127.0.0.1:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 1200.0,
        "currency": "USD",
        "products": [{"productId": "DB-I-01", "count": 1, "spec": "M"}],
    }

    response = integration_order_client.post("/order", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["orderId"].startswith("PX")
    assert "fail_reason" not in body


@pytest.mark.v2_integration
@pytest.mark.case(point="Integration: card number starting with 4 returns 400 and persists failed order")
def test_v2_integration_invalid_card_persists_fail_order(integration_order_client: TestClient, record_order_keyword):
    _maybe_clear_orders()

    ref = str(uuid4())
    record_order_keyword(ref)

    payload = {
        "reference": ref,
        "name": "Integration Invalid Card",
        "callback": "http://127.0.0.1:8100/callback",
        "cardNumber": "4111111111111111",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 20.0,
        "currency": "USD",
        "products": [{"productId": "DB-I-FAIL", "count": 1, "spec": "S"}],
    }

    response = integration_order_client.post("/order", json=payload)
    assert response.status_code == 400
    fail_body = response.json()
    assert fail_body["status"] == "FAIL"
    assert fail_body["fail_reason"] == "Unsupported card type"


@pytest.mark.v2_integration
@pytest.mark.case(point="Integration: GET /order reads and returns data from database")
def test_v2_integration_get_order_reads_from_db(integration_order_client: TestClient, record_order_keyword):
    _maybe_clear_orders()

    ref = str(uuid4())
    record_order_keyword(ref)

    create_payload = {
        "reference": ref,
        "name": "Integration Query Order",
        "callback": "http://127.0.0.1:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 88.8,
        "currency": "USD",
        "products": [{"productId": "DB-I-GET", "count": 1, "spec": "L"}],
    }

    create_response = integration_order_client.post("/order", json=create_payload)
    assert create_response.status_code == 201

    query_response = integration_order_client.get("/order", params={"reference": ref})
    assert query_response.status_code == 200
    data = query_response.json()
    assert data["reference"] == ref
    assert data["status"] == "SUCCESS"
    assert data["products"][0]["productId"] == "DB-I-GET"


@pytest.mark.v2_integration
@pytest.mark.case(point="Integration: duplicate reference second submit returns 400 and keeps only one record")
def test_v2_integration_duplicate_reference_conflict(integration_order_client: TestClient, record_order_keyword):
    _maybe_clear_orders()

    ref = str(uuid4())
    record_order_keyword(ref)
    payload = {
        "reference": ref,
        "name": "Integration Duplicate",
        "callback": "http://127.0.0.1:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 66.0,
        "currency": "USD",
        "products": [{"productId": "DB-I-DUP", "count": 1, "spec": "S"}],
    }

    first = integration_order_client.post("/order", json=payload)
    second = integration_order_client.post("/order", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400
    assert second.json()["fail_reason"] == "Order already exists"


@pytest.mark.v2_integration
@pytest.mark.case(point="Integration: product status becomes SHIPPED at 30s and DELIVERED at 60s, then order becomes COMPLETED")
def test_v2_integration_product_status_transition_30s_60s(
    integration_order_client: TestClient,
    record_order_keyword,
):
    _maybe_clear_orders()

    ref = str(uuid4())
    record_order_keyword(ref)
    payload = {
        "reference": ref,
        "name": "Integration Transition Order",
        "callback": "http://127.0.0.1:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 88.0,
        "currency": "USD",
        "products": [{"productId": "DB-I-TRANS", "count": 1, "spec": "M"}],
    }

    create_response = integration_order_client.post("/order", json=payload)
    assert create_response.status_code == 201

    initial = integration_order_client.get("/order", params={"reference": ref})
    assert initial.status_code == 200
    initial_body = initial.json()
    assert initial_body["status"] == "SUCCESS"
    assert initial_body["products"][0]["status"] == "PROCESSING"

    conn = order_db._conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE v2_orders SET created_at = NOW() - INTERVAL 31 SECOND WHERE reference = %s",
                (ref,),
            )
        conn.commit()
    finally:
        conn.close()

    order_db.apply_scheduled_transitions()

    shipped = integration_order_client.get("/order", params={"reference": ref})
    assert shipped.status_code == 200
    shipped_body = shipped.json()
    assert shipped_body["status"] == "SUCCESS"
    assert shipped_body["products"][0]["status"] == "SHIPPED"

    conn = order_db._conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE v2_orders SET created_at = NOW() - INTERVAL 61 SECOND WHERE reference = %s",
                (ref,),
            )
        conn.commit()
    finally:
        conn.close()

    order_db.apply_scheduled_transitions()

    delivered = integration_order_client.get("/order", params={"reference": ref})
    assert delivered.status_code == 200
    delivered_body = delivered.json()
    assert delivered_body["products"][0]["status"] == "DELIVERED"
    assert delivered_body["status"] == "COMPLETED"


@pytest.mark.v2_integration
@pytest.mark.case(point="Integration: in multi-product orders, order becomes COMPLETED only after all products are DELIVERED")
def test_v2_integration_order_completed_only_when_all_products_delivered(
    integration_order_client: TestClient,
    record_order_keyword,
):
    _maybe_clear_orders()

    ref = str(uuid4())
    record_order_keyword(ref)
    payload = {
        "reference": ref,
        "name": "Integration Multi Product Transition",
        "callback": "http://127.0.0.1:8100/callback",
        "cardNumber": "5555555555554444",
        "cvv": "123",
        "expiry": "12/28",
        "amount": 77.0,
        "currency": "USD",
        "products": [
            {"productId": "DB-I-MULTI-01", "count": 1, "spec": "M"},
            {"productId": "DB-I-MULTI-02", "count": 1, "spec": "L"},
        ],
    }

    create_response = integration_order_client.post("/order", json=payload)
    assert create_response.status_code == 201

    conn = order_db._conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE v2_orders SET created_at = NOW() - INTERVAL 31 SECOND WHERE reference = %s",
                (ref,),
            )
        conn.commit()
    finally:
        conn.close()

    order_db.apply_scheduled_transitions()

    conn = order_db._conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE v2_order_products p
                JOIN v2_orders o ON p.order_id = o.id
                SET p.status = 'DELIVERED'
                WHERE o.reference = %s AND p.product_id = %s
                """,
                (ref, "DB-I-MULTI-01"),
            )
        conn.commit()
    finally:
        conn.close()

    order_db.apply_scheduled_transitions()

    partial = integration_order_client.get("/order", params={"reference": ref})
    assert partial.status_code == 200
    partial_body = partial.json()
    assert partial_body["status"] == "SUCCESS"
    statuses = {item["productId"]: item["status"] for item in partial_body["products"]}
    assert statuses["DB-I-MULTI-01"] == "DELIVERED"
    assert statuses["DB-I-MULTI-02"] == "SHIPPED"

    conn = order_db._conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE v2_orders SET created_at = NOW() - INTERVAL 61 SECOND WHERE reference = %s",
                (ref,),
            )
        conn.commit()
    finally:
        conn.close()

    order_db.apply_scheduled_transitions()

    final_state = integration_order_client.get("/order", params={"reference": ref})
    assert final_state.status_code == 200
    final_body = final_state.json()
    assert final_body["status"] == "COMPLETED"
    assert all(item["status"] == "DELIVERED" for item in final_body["products"])
