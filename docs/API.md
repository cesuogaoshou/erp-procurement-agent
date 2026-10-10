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

## Planned

- `GET /suppliers`
- `POST /purchase-drafts`
- `POST /agent/runs`
- `GET /agent/runs/{id}`
- `GET /traces`
- `GET /purchase-orders`
- `POST /purchase-orders/{id}/approve`
- `POST /purchase-orders/{id}/reject`

Planned endpoints are not complete until tests and routes exist.
