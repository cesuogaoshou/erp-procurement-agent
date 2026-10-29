# API

Base path is `/`.

## Implemented In Phase 1

### `GET /health`

Returns service status.

### `POST /auth/login`

Demo-only login for the course environment. There is no full user management module. The server has two preset accounts:

- `buyer` / `buyer-pass`
- `approver` / `approver-pass`

Request:

```json
{"username": "buyer", "password": "buyer-pass"}
```

Returns a signed bearer token. Approval endpoints derive user and role from this server-signed token.

### `GET /materials`

Lists materials.

### `GET /inventory/{material_id}`

Returns inventory snapshot and available quantity.

### `POST /forecasts`

Request:

```json
{"material_id": 1, "horizon_days": 30}
```

Returns baseline cumulative demand, shortage, and model metadata.

### `POST /recommendations`

Request:

```json
{"material_id": 1, "quantity": 120, "required_in_days": 14, "budget": "8000.00"}
```

Returns eligible supplier recommendations and excluded candidates with reasons.

### `POST /purchase-drafts`

Requires a valid bearer token with the `buyer` role (401 without valid authentication, 403 for another role). Creates a persisted purchase draft after server-side evidence and supplier/material constraint validation. The order and its `created_draft` creator audit commit in one transaction. This does not place a real order and does not call external supplier systems.

Request:

```json
{
  "supplier_id": 1,
  "total_budget": "5000.00",
  "items": [{"material_id": 1, "quantity": "120"}],
  "idempotency_key": "demo-draft-001",
  "evidence_refs": ["<evidence_ref returned by POST /forecasts>", "<evidence_ref returned by POST /recommendations>"]
}
```

Replace the reference placeholders with current service responses; placeholder strings are rejected. Returns a draft purchase order with backend-calculated order quantity, unit price, line amount, and total amount. The backend rounds requested quantity up to satisfy supplier MOQ and `package_multiple`; repeating the same `idempotency_key` returns the existing order only to its creator, with no new order or creation audit. A different buyer receives 403 `order_owner_required`. Buyers can query their own orders through `GET /purchase-orders`. The Agent HTTP path also refuses to reassign an existing creator or duplicate the creation audit on replay.

### Approval Authentication

Approval endpoints use `Authorization: Bearer <token>` by default. The token is issued by `POST /auth/login` and signed by the server. Client-controlled `X-User-Id` and `X-User-Role` headers are not trusted in normal mode.

`X-User-Id` and `X-User-Role` are accepted only when the app is explicitly constructed with `allow_header_auth=True` for tests. Request body actor fields are never trusted for authorization.

### `POST /purchase-orders/{id}/submit`

Creator-only buyer transition from `draft` to `pending_approval`. A different buyer receives 403 `order_owner_required`, including when the order is already pending. The creator can repeat submission without adding a submission audit.

### `POST /purchase-orders/{id}/approve`

Approver-only transition from `pending_approval` to `approved`, with backend revalidation of order version, supplier status, supplier-material relationship, MOQ, package multiple, capacity, current quote, line amounts, and total amount.

Request:

```json
{"expected_order_version": 2, "idempotency_key": "approval-001"}
```

Returns the approved order with a generated `formal_order_number`.

### `POST /purchase-orders/{id}/reject`

Approver-only transition from `pending_approval` to `rejected`.

Request:

```json
{"expected_order_version": 2, "idempotency_key": "reject-001", "reason": "price too high"}
```

### `POST /agent/runs`

Buyer-only endpoint that runs the procurement Agent through the real LangGraph wrapper by default. It uses the configured OpenAI-compatible provider in normal runtime, or an injected provider in tests. Approval and rejection tools remain unavailable to the model.

Request:

```json
{"prompt": "为 MAT-001 创建采购草稿，采购数量120，交期20天，预算5000。", "total_budget": "5000.00", "use_langgraph": true}
```

Returns Agent run status, tool calls, run id, optional purchase order id, and whether real Function Calling / LangGraph execution was used.

### `GET /agent/runs`

Lists recent persisted Agent runs for the execution-record page.

### `GET /agent/runs/{id}`

Returns one persisted Agent run summary.

### `GET /agent/runs/{id}/traces`

Returns ordered tool traces for one run. `arguments` and `output` are parsed JSON. Forecast traces include model/config/fallback/evidence fields.

### `GET /purchase-orders`

Lists recent purchase orders with supplier name, status, version, formal order number, items, and persisted evidence JSON.

### `GET /demand-history/{material_id}`

Authenticated read-only endpoint for frontend analysis charts.

Query parameter:

```text
days=120
```

## Planned

- `GET /suppliers`

## Agent Tools

The Agent loop is service-level and verified with mock providers plus real DeepSeek/OpenAI-compatible Function Calling. Registered model tools are:

- `list_materials`
- `resolve_material`
- `get_inventory`
- `get_demand_forecast`
- `recommend_suppliers`
- `create_purchase_draft`

`get_demand_forecast` returns horizon, inventory snapshot, forecast demand, shortage, and a server-created evidence reference. `create_purchase_draft` validates that forecast evidence exists and that requested quantities do not exceed the server-calculated shortage. Approval and rejection endpoints are not exposed as model tools.

## 2026-10-29 safety contract

- A new direct draft requires `total_budget`, a positive finite Decimal (decimal strings accepted, at most two decimal places). Agent analysis permits `null`; writing then requires structured confirmation. Prompt text alone cannot establish the authoritative budget. The UI provides an explicit confirmation field. No model tool accepts `total_budget`: it is injected from the immutable run input. Recommendation `budget` is only a per-line filter and cannot exceed the confirmed total.
- Orders and run summaries expose nullable `total_budget`. Migration `20261029_0007` leaves historical values NULL; the UI displays unknown. Unknown-budget historical drafts cannot be approved (`budget_confirmation_required`); they may be rejected and recreated with a confirmed budget and a new key. Already-approved orders are not altered. Historical request fingerprints and pre-rounding quantities also remain unknown.
- Aggregate requested quantities by material before checking shortage, then round `ceil(max(sum(requested), MOQ) / package_multiple) * package_multiple` once. Check rounded capacity and recommendation coverage, calculate quoted line amounts using Decimal, and check the whole-order budget. Approval rechecks aggregate quantities, evidence, capacity, quotes and budget. Rejection remains available for invalid drafts.
- Replay requires the same creator and canonical request content. Decimal forms such as `120.0`/`120.00` and duplicate-line decompositions with equal totals are equivalent. Changed content returns 409 `idempotency_payload_conflict`; legacy identity cannot be verified and returns 409 `idempotency_payload_unknown`. Only a specific order-idempotency unique-key race is recovered, using savepoint rollback and current reads of the winner, its items and creator.
- Every tool uses a local Pydantic parameter model; published JSON Schema is generated from that same model. Unknown fields, invalid structures, nonpositive or nonfinite quantities/budgets, invalid IDs, oversized strings and invalid horizons/deadlines are rejected as `tool_parameter_error` before business logic. Evidence numeric fields are validated separately, including on replay.
- The default Agent limit is 8 tool calls and a 180-second loop deadline, in addition to the provider's 30-second request timeout. Explicit lower test limits remain supported. Forecast output already includes inventory; observations and latest evidence per material are reused. Exhaustion persists a run and traces and returns HTTP 409. Other controlled outcomes include `tool_error`, `provider_error`, `failed`, `timeout`, `completed`, `no_shortage`, and `no_qualified_suppliers`; failure runs remain queryable by their creator.
