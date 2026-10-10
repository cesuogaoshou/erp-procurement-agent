# Data Dictionary

All current data is simulated using seed `20261010`.

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

## Phase 1 Simplification

Confirmed inbound supply is not modeled yet. Shortage calculation therefore uses:

`available supply = on_hand - reserved`
