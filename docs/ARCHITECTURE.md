# Architecture

## Layers

- API layer: FastAPI routes, demo token authentication, request validation, and error mapping.
- Service layer: inventory, forecast, shortage, recommendation, draft, approval, permissions, and audit behavior.
- Algorithm layer: baseline forecast, shortage formula, supplier scoring, and evaluation metrics.
- Model layer: SQLAlchemy models and database session management.
- Agent layer: provider abstraction, tool schemas, bounded tool loop, and later trace persistence.

## Data Flow

1. A request resolves a material.
2. Inventory service returns on-hand, reserved, and available quantity.
3. Forecast service predicts cumulative demand for a planning horizon.
4. Shortage algorithm calculates shortage using safety stock and available supply.
5. Recommendation service filters supplier candidates and scores eligible suppliers.
6. Draft creation validates evidence again before persisting a purchase draft.
7. A buyer submits the draft for approval using the authenticated user context.
8. An approver approves or rejects the pending order. Approval revalidates the stored version, current quote, supplier relationship, MOQ, capacity, line amounts, and total. Approved orders receive a formal order number.
9. The Agent loop can call read-only tools first and then `create_purchase_draft`; approval actions remain outside the model tool surface.

## Boundaries

LLM output is treated as untrusted input. It cannot execute arbitrary SQL, approve orders, calculate prices, calculate scores, or override backend rules.

Authentication context is also treated as server-owned. Normal API mode uses a server-signed bearer token issued by the demo login endpoint. Client-controlled `X-User-Id` and `X-User-Role` headers are accepted only when explicit test mode is enabled, and body-supplied user or role fields are ignored.

Phase 1 deliberately excludes in-transit supply. The data model can be extended later with confirmed inbound order snapshots.

## Approval Consistency

Approval state changes, approval records, and audit logs are written in one database transaction. Repeated approval/rejection requests use `idempotency_key`; stale versions and non-pending orders are rejected. MySQL row-lock concurrency behavior still requires real MySQL verification when credentials are available.

## Agent Boundary

The Agent provider interface is implemented with a mock provider for offline tests. It has a hard maximum tool-call count and rejects any tool name not in the registered schema. The available tool set intentionally excludes approval and rejection. Real Function Calling with an external LLM is not accepted until credentials are configured and provider-specific tests run.
