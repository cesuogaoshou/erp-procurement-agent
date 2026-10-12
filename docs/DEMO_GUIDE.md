# Demo Guide

## Configuration

Create `.env` from `.env.example` or export equivalent variables before starting new processes. The backend loads `.env` from the project root without overriding already-set process variables.

Required for real-model Agent runs:

```powershell
DATABASE_URL=sqlite+pysqlite:///./erp_demo.sqlite
ERP_AUTH_SECRET=replace-with-local-demo-secret
OPENAI_API_KEY=<set locally, never commit>
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL_USER=deepseek-v4-flash
```

Model priority is `OPENAI_MODEL_USER` first, then `OPENAI_MODEL`. Missing `OPENAI_BASE_URL` or model configuration returns an explicit backend error and does not print secrets.

## Initialize Demo Data

Demo reset is intentionally limited to database names or SQLite files containing `demo`.

```powershell
python -m backend.app.db.init_demo_data --database-url "sqlite+pysqlite:///./erp_demo.sqlite"
```

For MySQL, use a clearly named demo schema, for example:

```powershell
$env:DATABASE_URL = "mysql+pymysql://erp_user:<password>@127.0.0.1:3306/erp_demo"
python -m alembic upgrade head
python -m backend.app.db.init_demo_data --database-url $env:DATABASE_URL
```

Do not point demo reset at an existing production, shared, or non-demo database.

## Start

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`.

## Login

- Buyer: `buyer` / `buyer-pass`
- Approver: `approver` / `approver-pass`

## Procurement Loop

1. Login as buyer.
2. On `智能采购`, run:

```text
Use material_id 1 directly. Recommend a supplier for 120 units required in 20 days with budget 5000. Create exactly one purchase draft if backend forecast evidence supports it.
```

3. Confirm the page shows `draft_created`, a run id, a draft order id, supplier, amount, and tool trace.
4. Open `采购审批`.
5. Submit the draft as buyer.
6. Login as approver.
7. Approve the pending order.
8. Confirm the order status is `approved` and a `PO-` formal order number is shown.

## Query And Analysis

1. Open `数据分析`.
2. Select a material and horizon.
3. Click `分析`.
4. Confirm inventory, forecast demand, shortage, selected model, fallback reason, and supplier recommendations are visible.

## Latest Local Screenshot Evidence

- `reports/generated/screenshots/01-buyer-agent-home.png`
- `reports/generated/screenshots/02-analysis-page.png`
- `reports/generated/screenshots/03-approval-approved-order.png`

The latest browser DOM validation also verified a real Agent draft run, buyer submit, approver approval, and formal order `PO-000002` on the local demo service.
