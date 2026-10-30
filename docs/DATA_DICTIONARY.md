# Data Dictionary

## V2 independent simulation (2026-10-29 release)

The V1 definitions and frozen files below remain unchanged. V2 lives in `data/v2/raw/`, with the same material codes, supplier IDs/names and activation flags. Only supplier quotes and performance change; the five invariant files are byte-identical to V1. See `docs/V2_DATA_DESIGN_20261029.md` and `docs/V2_RUNBOOK.md` for profiles, constraints, independent label conditions, hashes and empty-only MySQL import.

V2 adds `scenarios.json` (80 frozen business scenarios; acceptable/eligible supplier sets and explicit independent thresholds) and `manifest.json` (version `simulated_procurement_v2_20261029.1`, independent seed `20261029`, dates, full parameters, generator/design/source/output SHA-256, row counts, natural primary keys). `supplier_materials.csv` and `supplier_performance.csv` retain the existing columns below. All data is autonomously generated teaching simulation, never described as enterprise or public procurement records.

Frozen V1 data is simulated using seed `20261010`. Its CSV exports are written with UTF-8 encoding to `data/raw/`.

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
- `package_multiple`: order quantity package multiple; draft creation rounds up to satisfy both MOQ and this multiple.
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
- `status`: `draft`, `pending_approval`, `approved`, or `rejected`.
- `idempotency_key`: unique write key for retry-safe draft creation.
- `total_amount`: backend-calculated order amount.
- `evidence_refs_json`: references to recommendation or forecast evidence.
- `version`: optimistic version placeholder for later approval.
- `formal_order_number`: generated only on approval.

### `purchase_order_items`

- `order_id`: purchase order reference.
- `material_id`: material reference.
- `quantity`: backend-validated order quantity after MOQ/package-multiple rounding.
- `unit_price`: backend-selected supplier quote.
- `line_amount`: backend-calculated quantity times unit price.

### `agent_runs`

- `id`: Agent run primary key.
- `status`: run terminal or controlled business state.
- `prompt`: original user request.
- `state_json`: persisted run state.
- `purchase_order_id`: linked draft order when one was created.

### `tool_traces`

- `agent_run_id`: Agent run reference.
- `tool_name`: executed tool.
- `arguments_json`: model-supplied arguments after schema parsing.
- `output_json`: deterministic backend tool result.
- `error`: captured tool error, if any.

## Phase 1 Simplification

Confirmed inbound supply is not modeled yet. Shortage calculation therefore uses:

`available supply = on_hand - reserved`
