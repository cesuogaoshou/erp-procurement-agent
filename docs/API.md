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

Creates a persisted purchase draft after server-side evidence and supplier/material constraint validation. This does not place a real order and does not call external supplier systems.

Request:

```json
{
  "supplier_id": 1,
  "items": [{"material_id": 1, "quantity": "120"}],
  "idempotency_key": "demo-draft-001",
  "evidence_refs": ["recommendation:demo"]
}
```

Returns a draft purchase order with backend-calculated unit price, line amount, and total amount. Repeating the same `idempotency_key` returns the existing draft.

### Approval Authentication

Approval endpoints use `Authorization: Bearer <token>` by default. The token is issued by `POST /auth/login` and signed by the server. Client-controlled `X-User-Id` and `X-User-Role` headers are not trusted in normal mode.

`X-User-Id` and `X-User-Role` are accepted only when the app is explicitly constructed with `allow_header_auth=True` for tests. Request body actor fields are never trusted for authorization.

### `POST /purchase-orders/{id}/submit`

Buyer-only transition from `draft` to `pending_approval`.

### `POST /purchase-orders/{id}/approve`

Approver-only transition from `pending_approval` to `approved`, with backend revalidation of order version, supplier status, supplier-material relationship, MOQ, capacity, current quote, line amounts, and total amount.

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

## Planned

- `GET /suppliers`
- `POST /agent/runs`
- `GET /agent/runs/{id}`
- `GET /traces`
- `GET /purchase-orders`

Planned endpoints are not complete until tests and routes exist.

## Agent Tools

The current Agent loop is service-level only and verified with a mock provider. Registered model tools are:

- `list_materials`
- `resolve_material`
- `get_inventory`
- `get_demand_forecast`
- `recommend_suppliers`
- `create_purchase_draft`

`get_demand_forecast` returns horizon, inventory snapshot, forecast demand, shortage, and a server-created evidence reference. `create_purchase_draft` validates that forecast evidence exists and that requested quantities do not exceed the server-calculated shortage. Approval and rejection endpoints are not exposed as model tools.
