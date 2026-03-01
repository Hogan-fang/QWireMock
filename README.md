# QWire Mock

QWire Mock provides two FastAPI services:

- Order API (`POST /order`, `GET /order`) with MySQL persistence
- Callback API (`POST /callback`, `GET /check`) for callback receiving and log-only check behavior

Current package version: `2.0.0`.

Core configuration is now centralized in `config.yaml`.

## Requirements

- Python 3.9+
- MySQL (default database: `qwire`)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt
```

## Run Services

Run both services (default):

```bash
python -m qwire_mock
```

Run one service only:

```bash
python -m qwire_mock --service callback
python -m qwire_mock --service order
```

Set host:

```bash
python -m qwire_mock --host 127.0.0.1 --service all
```

Default ports:

- Callback API: `8100`
- Order API: `9100`

## API Summary

### Order API (`:9100`)

- `POST /order`
  - Success: `201`, `status="SUCCESS"`
  - Invalid card (`cardNumber` starts with `4`): `400`, `status="FAIL"`, `fail_reason="Unsupported card type"`
  - Duplicate reference: `400`, `status="FAIL"`, `fail_reason="Order already exists"`
- `GET /order?reference=<uuid>`
  - Found: `200`
  - Invalid UUID: `400`, `fail_reason="invalid UUID string"`
  - Not found: `404`, `fail_reason="Order not found"`

Order status lifecycle:

- Order: `SUCCESS -> COMPLETED` (or `FAIL` on create failure)
- Product: `PROCESSING -> SHIPPED -> DELIVERED`

Scheduler transition rules:

- after 30s: product `PROCESSING -> SHIPPED`
- after 60s: product `SHIPPED/PROCESSING -> DELIVERED`
- when all products are `DELIVERED`: order `SUCCESS -> COMPLETED`

Callback events sent by Order API:

- `ORDER_SUCCESS`
- `ORDER_SHIPPED`
- `ORDER_DELIVERED`
- `ORDER_COMPLETED`

If order `amount >= QWIRE_V2_CALLBACK_SKIP_AMOUNT_GTE` (default `1000`), callback dispatch is skipped.

### Callback API (`:8100`)

- `POST /callback`
  - Valid payload: `200`, body `{ "message": "OK" }`
  - Invalid payload: `400`, body with validation errors
- `GET /check?reference=<uuid>`
  - Always `404` (callback records are log-only and not queryable)

## Logging

Service logs are written to project root:

- `order.log`
- `callback.log`

Logged events include:

- service startup/shutdown
- request payloads
- response payloads
- callback dispatch and callback response details

JSON bodies are pretty-printed in logs.

Optional log path environment variables:

- `QWIRE_V2_ORDER_LOG` (default `order.log`)
- `QWIRE_V2_CALLBACK_LOG` (default `callback.log`)

## Configuration

### Configuration File (`config.yaml`)

The project root `config.yaml` is the primary configuration source for:

- server host and ports
- MySQL connection
- order scheduler and callback threshold
- log format and log file paths

Use a custom file path with:

- `QWIRE_CONFIG_FILE=/path/to/your-config.yaml`

### Environment Variable Overrides

Environment variables are still supported as overrides for compatibility:

MySQL:

- `QWIRE_MYSQL_HOST` (default `localhost`)
- `QWIRE_MYSQL_PORT` (default `3306`)
- `QWIRE_MYSQL_USER` (default `qwire`)
- `QWIRE_MYSQL_PASSWORD` (default `Qwire2026`)
- `QWIRE_MYSQL_DATABASE` (default `qwire`)

Order scheduler and callback policy:

- `QWIRE_V2_POLL_INTERVAL_SECONDS` (default `5`)
- `QWIRE_V2_CALLBACK_SKIP_AMOUNT_GTE` (default `1000`)

Tests:

- `QWIRE_V2_CLEAR_DB_BEFORE_TEST=1` to clear `v2_orders` before each integration test (default is no clearing)

## Development

Run tests:

```bash
pytest
```

Run a specific group:

```bash
pytest -m v2_integration
```

## Project Structure

```text
QWireMock/
├── config.yaml
├── src/qwire_mock/
│   ├── __main__.py
│   ├── callback_service.py
│   ├── order_service.py
│   ├── order_db.py
│   └── schemas.py
├── tests/
├── blueprint/
│   ├── order_server.yaml
│   └── callback_server.yaml
└── README.md
```
