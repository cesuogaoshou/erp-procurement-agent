# API

Base path is `/`.

## Implemented In Phase 1

### `GET /health`

Returns service status.

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

## Planned

- `GET /suppliers`
- `POST /agent/runs`
- `GET /agent/runs/{id}`
- `GET /traces`
- `GET /purchase-orders`
- `POST /purchase-orders/{id}/approve`
- `POST /purchase-orders/{id}/reject`

Planned endpoints are not complete until tests and routes exist.
