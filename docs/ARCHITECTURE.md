# Architecture

## Layers

- API layer: FastAPI routes, authentication context placeholder, request validation, and error mapping.
- Service layer: inventory, forecast, shortage, recommendation, draft, approval, permissions, and audit behavior.
- Algorithm layer: baseline forecast, shortage formula, supplier scoring, and evaluation metrics.
- Model layer: SQLAlchemy models and database session management.
- Agent layer: later-phase tool schemas, provider calls, run state, and traces.

## Data Flow

1. A request resolves a material.
2. Inventory service returns on-hand, reserved, and available quantity.
3. Forecast service predicts cumulative demand for a planning horizon.
4. Shortage algorithm calculates shortage using safety stock and available supply.
5. Recommendation service filters supplier candidates and scores eligible suppliers.
6. Draft creation validates evidence again before persisting a purchase draft.
7. Later phases add Agent orchestration and approval workflows around these services.

## Boundaries

LLM output is treated as untrusted input. It cannot execute arbitrary SQL, approve orders, calculate prices, calculate scores, or override backend rules.

Phase 1 deliberately excludes in-transit supply. The data model can be extended later with confirmed inbound order snapshots.
