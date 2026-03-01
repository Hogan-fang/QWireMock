# Python Mock Service Build Plan

## 1. Goals and Scope

### 1.1 Goals
Build an independently runnable Mock platform that supports:
1. Receiving and processing simulated order requests (create, query, status transition).
2. Triggering asynchronous callbacks according to service contracts to simulate real notification flows.
3. Stable and reproducible test behavior (controllable delay, failure injection, retry behavior).

### 1.2 In Scope
- HTTP APIs (order API + callback receiving API)
- Order state machine and persistence layer (MySQL)
- Callback record output (log file only, no DB persistence)
- Callback scheduler (retry/backoff/timeout design)
- Unified configuration, logging, error handling, and health checks
- Test and contract validation skeleton
- Readable request/response logging for all API traffic

### 1.3 Out of Scope (Current Phase)
- Production-grade authentication/authorization (for example OAuth2)
- Distributed MQ and multi-instance consistency
- Real external business system integration

## 2. Core Architecture
- `order-service`: handles order lifecycle and query.
- `callback-server`: receives callbacks and writes readable logs, without DB persistence for callback payloads.
- `shared`: shared models, error semantics, configuration, and utility logic.
- `scheduler`: asynchronous callback task orchestration.
- `tests`: unit, integration, and contract tests.

### 2.1 Contract Baseline (Reference)
- Order service: `order_server.yaml`
  - `GET /order?reference={uuid}`
  - `POST /order`
- Callback service: `callback_server.yaml`
  - `GET /check?reference={uuid}`
  - `POST /callback`
- This plan and all spec files follow these endpoints, fields, and response codes as the baseline.

## 3. Key Capability Checklist
1. **Order Management**: create and query orders (status reflected through order logic and callback flow).
2. **Callback Simulation**: publish callbacks by rule, with retry and dead-letter behavior design.
3. **Failure Injection**: configurable simulation of 4xx/5xx cases.
4. **Observability**: structured logs, request trace ID placeholder, and metric hooks.
5. **Testability**: fixed random seed, time control, and scenario scripting.

## 4. Phased Implementation

### Phase 0: Project Skeleton
- Build directory structure, dependency management, and configuration template.
- Define shared data models and error semantics.

### Phase 1: Order Service MVP
- Implement order create/query APIs.
- Implement order state model and core validation.

### Phase 2: Callback Flow MVP
- Implement callback receiver and sender sides.
- Implement retry strategy (exponential backoff) and timeout mechanism.

### Phase 3: Stability and Testing
- Implement sample unit tests, integration tests, and contract tests.

### Phase 4: Runtime and Delivery
- Complete health checks and runtime scripts.
- Deliver usage guide and sample scenarios.

## 5. Definition of Done (DoD)
- All public APIs have clear request/response contracts.
- Order/product status transition rules are covered by automated tests.
- Callback retry and failure paths are configurable and verifiable.
- Logs can trace one order end-to-end.
- Documentation enables a new member to run locally within 30 minutes.
- Full test suite exists and outputs a concrete execution report showing each test step and related order keywords.
- Callback request and response can be searched and audited in log files.

## 6. Database Connection Settings
- host: localhost
- port: 3306
- user: qwire
- password: Qwire2026
- database: qwire

## 7. Documentation Rule
- PLAN and spec documents are maintained in bilingual form (Chinese + English); other documents are English only.
