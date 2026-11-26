# TAHIRA'S CLOSSET — Inventory 2.0

Full-stack closset storefront and admin app (FastAPI + SQLite) with Inventory 2.0.

## Run (Windows / PowerShell)
```powershell
cd C:\Users\AMINILOGY\Downloads\Tahiras-Closset\Tahiras-Closset
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

Or double-click `START-DEMO.bat`.

## URLs
- Storefront: http://127.0.0.1:8001
- Admin: http://127.0.0.1:8001/admin
- Login: http://127.0.0.1:8001/login
- API docs: http://127.0.0.1:8001/docs

Default demo admin (change in production):
- Username: `tahira`
- Password: `Tahira@123`

Environment variables: `CLOSSET_ADMIN_USER`, `CLOSSET_ADMIN_PASSWORD`, `CLOSSET_TOKEN_SECRET`.

## Inventory 2.0
- Product variants (size/colour) with per-variant SKU, stock, cost/selling override, barcode, threshold, active status.
- Inventory matrix in admin with direct cell editing.
- Auditable stock ledger for opening stock, restocking, sale/reservation events, returns, damage/loss, manual corrections, transfers.
- Restock interface with supplier/reference/notes.
- Low-stock/out-of-stock dashboard and lists.
- Inventory dashboard with real DB metrics and valuation.
- Search/filter by product, SKU, barcode, category, status, size, colour, active.
- Bulk variant updates, CSV export/import with preview and validation.
- Inventory history with filters and CSV export.

## Database migration & data preservation
- Existing SQLite DB is preserved; no empty DB replacement.
- On startup, inventory schema is ensured and legacy products are migrated into `inventory_variants`.
- Existing product stock is preserved as opening stock in the ledger (recorded as `opening_stock`).
- Products without size/colour get a `Default / Default` variant.
- Migration is idempotent via `inventory_migrations` key.

## Tests
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pytest -q
```
