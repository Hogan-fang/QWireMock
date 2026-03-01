# QWireMock Refactoring Blueprint (Independent from Existing Code)

This directory plans a **Python-based** simulation platform including:
- Mock Order Processing Service (Order Service)
- Mock Initiator Callback Service (Callback Server)

> Constraint: this blueprint does not depend on, reference, or modify any existing implementation in this repository.

## Document Index
- `PLAN.md`: master implementation plan (scope, milestones, deliverables)
- `specs/order-service.spec.yaml`: order processing service specification
- `specs/callback-server.spec.yaml`: callback service specification
- `specs/shared-contracts.spec.yaml`: shared cross-module contracts and conventions
- `structure/target-directory-structure.md`: target project structure

## English Version Index
- `README.en.md`: English index
- `PLAN.en.md`: master implementation plan
- `specs/order-service.spec.en.yaml`: order service spec
- `specs/callback-server.spec.en.yaml`: callback server spec
- `specs/shared-contracts.spec.en.yaml`: shared contracts spec
- `structure/target-directory-structure.en.md`: target directory structure plan
