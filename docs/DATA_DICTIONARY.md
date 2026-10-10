# Data Dictionary

All current data is simulated using seed `20261010`. CSV exports are written with UTF-8 encoding to `data/raw/`.

## Generation Parameters

- Materials: 10.
- Suppliers: 10.
- Demand history: 540 daily records per material, ending on 2026-10-09.
- Demand pattern: trend, weekly seasonality, annual bump, noise, and intermittent spikes for selected materials.
- Inventory snapshot date: 2026-10-10.
- Time split: train, validation, and test are exported in `data/raw/data_splits.csv`.

## Tables

### `materials`

- `id`: internal primary key.
- `code`: material code.
- `name`: material display name.
- `unit`: unit of measure.
- `safety_stock`: safety stock used in shortage calculation.

### `inventory`

- `material_id`: material reference.
- `on_hand`: current stock.
- `reserved`: reserved stock.
- `version`: optimistic version placeholder.
- `updated_at`: inventory update timestamp.

### `demand_history`

- `material_id`: material reference.
- `demand_date`: historical consumption date.
- `quantity`: actual simulated consumption.

### `suppliers`

- `name`: supplier name.
- `active`: whether supplier can be selected.

### `supplier_materials`

- `supplier_id`: supplier reference.
- `material_id`: material reference.
- `unit_price`: current quoted unit price.
- `lead_time_days`: quoted delivery lead time.
- `moq`: minimum order quantity.
- `capacity`: maximum supply capacity for the planning request.

### `supplier_performance`

- `avg_price`: historical average price reference.
- `promised_deliveries`: historical delivery count.
- `on_time_deliveries`: on-time delivery count.
- `inspected_quantity`: inspected quantity.
- `accepted_quantity`: quality accepted quantity.
- `complaint_count`: historical complaint count.

### `purchase_orders`

- `supplier_id`: one supplier per draft or formal order.
- `status`: currently `draft` only in Phase 1.
- `idempotency_key`: unique write key for retry-safe draft creation.
- `total_amount`: backend-calculated order amount.
- `evidence_refs_json`: references to recommendation or forecast evidence.
- `version`: optimistic version placeholder for later approval.

### `purchase_order_items`

- `order_id`: purchase order reference.
- `material_id`: material reference.
- `quantity`: requested quantity.
- `unit_price`: backend-selected supplier quote.
- `line_amount`: backend-calculated quantity times unit price.

## Phase 1 Simplification

Confirmed inbound supply is not modeled yet. Shortage calculation therefore uses:

`available supply = on_hand - reserved`
