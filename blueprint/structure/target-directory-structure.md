# Target Directory Structure (Python Mock Platform)

> This structure is a recommendation for future implementation and does not depend on existing code.

## Recommended Tree

```text
mock-platform/
  pyproject.toml
  README.md
  .env.example

  src/
    mock_platform/
      __init__.py

      app/
        order_service/
          api/
            routes.py
            schemas.py
          domain/
            models.py
            state_machine.py
            services.py
          infra/
            repository.py
            memory_store.py
            file_store.py
          main.py

        callback_server/
          api/
            routes.py
            schemas.py
          domain/
            policies.py
            services.py
          infra/
            record_store.py
          main.py

      shared/
        config.py
        errors.py
        logging.py
        contracts/
          order.py
          callback.py

      scheduler/
        callback_dispatcher.py
        retry.py
        queue.py

  specs/
    order-service.spec.yaml
    callback-server.spec.yaml
    shared-contracts.spec.yaml

  tests/
    unit/
      order_service/
      callback_server/
      shared/
    integration/
      test_order_to_callback_flow.py
    contract/
      test_api_contracts.py

  scripts/
    run_order_service.sh
    run_callback_server.sh
    run_all_tests.sh
```

## Layering Constraints
- `api`: protocol encode/decode and input validation only
- `domain`: business rules only; framework-independent
- `infra`: storage, I/O, and external integration details
- `shared`: reusable cross-service components and contracts
- `scheduler`: async dispatch, retry, and backoff handling

## Startup Modes
- Mode A: run `order_service` and `callback_server` separately (closer to distributed deployment)
- Mode B: single process with multiple routers (simpler local debugging)

## Naming and Contract Principles
- Unified API prefix: `/v1`
- Shared error codes live in `shared/errors.py`
- Unified trace header: `X-Trace-Id`
- Prefer backward-compatible field evolution (additive changes only)
