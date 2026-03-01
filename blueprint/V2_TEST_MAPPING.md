# V2 Test Mapping and Case Notes (Merged)

## Coverage Overview

- Scope: `tests/test_v2_*.py`
- Current total: 19
  - `test_v2_order_service.py`: 9
  - `test_v2_order_service_integration.py`: 6
  - `test_v2_callback_service.py`: 3
  - `test_v2_execution_report.py`: 1

## Quick Run Commands

Run from project root (`QWireMock/QWireMock`):

- Full v2 suite:
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_v2_*.py -v`
- Order service unit/API tests only:
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_v2_order_service.py -v`
- Order service integration tests only (real DB):
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_v2_order_service_integration.py -v`
- Callback service tests only:
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_v2_callback_service.py -v`
- Execution report sample only:
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/test_v2_execution_report.py -v`

Optional: clear DB before integration tests (default is no clear):

- `QWIRE_V2_CLEAR_DB_BEFORE_TEST=1 PYTHONPATH=src .venv/bin/python -m pytest tests/test_v2_order_service_integration.py -v`

## 1) Order Service Tests (Unit/API)

Source file: `tests/test_v2_order_service.py`

| Test Case | Functional Point |
|---|---|
| `test_v2_create_order_success_returns_201_and_masked_card` | Validates successful `POST /order` (201), `SUCCESS` status, card masking, no sensitive fields, and `ORDER_SUCCESS` callback event. |
| `test_v2_create_order_conflict_returns_400` | Validates duplicate `reference` returns 400 with `Order already exists`. |
| `test_v2_create_order_invalid_card_returns_400` | Validates card numbers starting with `4` fail with 400 + `FAIL` + reason. |
| `test_v2_create_order_invalid_uuid_returns_422` | Validates invalid UUID in `POST /order` body returns 422 from framework validation. |
| `test_v2_get_order_invalid_uuid_returns_400` | Validates invalid UUID in `GET /order` query returns 400 + `invalid UUID string`. |
| `test_v2_get_order_not_found_returns_404` | Validates `GET /order` returns 404 + `Order not found` for absent order. |
| `test_v2_get_order_found_returns_200` | Validates successful `GET /order` returns 200 with `SUCCESS` and no `fail_reason`. |
| `test_v2_create_then_get_order_flow` | Validates create-then-query consistency (`reference/orderId`). |
| `test_v2_dispatch_callback_skip_by_amount_policy` | Validates callback threshold policy: high amount skips, low amount triggers. |

## 2) Order Service Integration Tests (Real DB)

Source file: `tests/test_v2_order_service_integration.py`

| Test Case | Functional Point |
|---|---|
| `test_v2_integration_create_order_persists_db` | Validates successful `POST /order` persistence into `v2_orders`/`v2_order_products` and `SUCCESS` response. |
| `test_v2_integration_invalid_card_persists_fail_order` | Validates invalid-card failure and failed-order persistence. |
| `test_v2_integration_get_order_reads_from_db` | Validates `GET /order` reads and returns persisted data. |
| `test_v2_integration_duplicate_reference_conflict` | Validates duplicate `reference` second submit returns 400 conflict. |
| `test_v2_integration_product_status_transition_30s_60s` | Validates timed product transitions `PROCESSING -> SHIPPED(30s) -> DELIVERED(60s)` and order `SUCCESS -> COMPLETED`. |
| `test_v2_integration_order_completed_only_when_all_products_delivered` | Validates in multi-product orders that completion occurs only after all products are `DELIVERED`. |

## 3) Callback Service Tests

Source file: `tests/test_v2_callback_service.py`

| Test Case | Functional Point |
|---|---|
| `test_v2_callback_receive_returns_ok` | Validates valid `POST /callback` returns 200; repeated callbacks are accepted in log-only mode. |
| `test_v2_check_not_found_returns_404` | Validates `GET /check` consistently returns 404 in log-only mode. |
| `test_v2_callback_invalid_payload_returns_400` | Validates invalid `POST /callback` payload returns 400 with validation details. |

## 4) Execution Report Test

Source file: `tests/test_v2_execution_report.py`

| Test Case | Functional Point |
|---|---|
| `test_generate_v2_execution_report` | Validates execution-trace recording: captures `reference/orderId`, callback succeeds, and `/check` remains 404 in log-only mode. |

## 5) Mapping to Plan Key Items

- API contract coverage (order/callback/check)
- Error-path coverage (400/404)
- State transition coverage (order `SUCCESS->COMPLETED`, product `PROCESSING->SHIPPED->DELIVERED`)
- Callback log-output coverage (non-persistent)
- Order API integration behavior coverage
- Test-report output coverage (with order keywords)
