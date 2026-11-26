from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .analytics import dashboard_stats
from .ledger import list_movements
from .models import ensure_inventory_schema, migrate_existing_products_to_variants, sync_product_stock
from .schemas import BulkProductUpdate, BulkVariantUpdate, RestockRequest, StockAdjustRequest, StockDeltaRequest, VariantUpdate
from .service import adjust_by_delta, change_variant_stock, get_matrix, get_variant, list_inventory, list_variant_rows, resolve_variant


router = APIRouter(prefix="/api/inventory", tags=["inventory"])
security = HTTPBearer(auto_error=False)


def _main():
    import backend.app.main as main  # lazy import to avoid circular during module init
    return main


def require_admin(creds: HTTPAuthorizationCredentials = Depends(security)):
    main = _main()
    return main.get_admin(creds)


def db_conn():
    main = _main()
    con = main.db()
    try:
        yield con
    finally:
        con.close()


def admin_user(request: Request) -> str:
    main = _main()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        # sessions store timestamp; we just need identity - use configured admin user
        if token in main.sessions:
            return main.ADMIN_USER
    return "administrator"


@router.get("/dashboard")
def inventory_dashboard(_=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        return dashboard_stats(con)
    finally:
        con.close()


@router.get("")
def inventory_list(
    q: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    active: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _=Depends(require_admin),
):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        return list_inventory(con, q=q, category=category, status=status, size=size, color=color, active=active, limit=limit, offset=offset)
    finally:
        con.close()


@router.get("/variants")
def inventory_variants(
    q: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _=Depends(require_admin),
):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        return list_variant_rows(con, status=status, q=q, limit=limit, offset=offset)
    finally:
        con.close()


@router.get("/low-stock")
def inventory_low_stock(q: Optional[str] = None, limit: int = 200, offset: int = 0, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        return list_variant_rows(con, status="low_stock", q=q, limit=limit, offset=offset)
    finally:
        con.close()


@router.get("/out-of-stock")
def inventory_out_of_stock(q: Optional[str] = None, limit: int = 200, offset: int = 0, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        return list_variant_rows(con, status="out_of_stock", q=q, limit=limit, offset=offset)
    finally:
        con.close()


@router.get("/history")
def inventory_history(
    product_id: Optional[int] = None,
    variant_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    sku: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _=Depends(require_admin),
):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        items, total = list_movements(con, limit=limit, offset=offset, product_id=product_id, variant_id=variant_id, movement_type=movement_type, sku=sku, date_from=date_from, date_to=date_to)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    finally:
        con.close()


@router.get("/export")
def inventory_export(_=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        rows = con.execute(
            """
            SELECT p.id AS product_id, p.name AS product_name, p.sku AS product_sku, p.category, p.brand,
                   p.supplier AS product_supplier, p.active AS product_active,
                   v.id AS variant_id, v.size, v.color, v.variant_sku, v.barcode,
                   v.stock_quantity, v.low_stock_threshold, v.cost_price, v.selling_price, v.is_active AS variant_active
            FROM products p LEFT JOIN inventory_variants v ON v.product_id=p.id
            ORDER BY p.name, v.size, v.color
            """
        ).fetchall()
        output = io.StringIO()
        fieldnames = ["product_id","product_name","product_sku","category","brand","product_supplier","product_active","variant_id","size","color","variant_sku","barcode","stock_quantity","low_stock_threshold","cost_price","selling_price","variant_active"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventory-export.csv"})
    finally:
        con.close()


@router.get("/history/export")
def inventory_history_export(
    product_id: Optional[int] = None,
    variant_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    sku: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    _=Depends(require_admin),
):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        items, _ = list_movements(con, limit=10000, offset=0, product_id=product_id, variant_id=variant_id, movement_type=movement_type, sku=sku, date_from=date_from, date_to=date_to)
        output = io.StringIO()
        fields = ["id","created_at","product_name","product_sku","variant_sku","size","color","movement_type","quantity_change","quantity_before","quantity_after","reason","administrator","reference_number","supplier","unit_cost","notes"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, "") for k in fields})
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventory-history.csv"})
    finally:
        con.close()


@router.get("/matrix/{product_id}")
def inventory_matrix(product_id: int, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        return get_matrix(con, product_id)
    finally:
        con.close()


@router.post("/restock")
def inventory_restock(payload: RestockRequest, request: Request, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        variant = resolve_variant(con, product_id=payload.product_id, variant_id=payload.variant_id, size=payload.size, color=payload.color)
        result = adjust_by_delta(
            con,
            variant=variant,
            delta=payload.quantity_received,
            movement_type="restocking",
            reason=payload.notes or "Restock received",
            administrator=admin_user(request),
            reference_number=payload.reference_number,
            notes=payload.notes,
            supplier=payload.supplier,
            unit_cost=payload.cost_price,
        )
        con.commit()
        return {"ok": True, **result}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@router.post("/adjust")
def inventory_adjust(payload: StockAdjustRequest, request: Request, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        variant = resolve_variant(con, product_id=payload.product_id, variant_id=payload.variant_id, size=payload.size, color=payload.color)
        result = change_variant_stock(
            con,
            variant=variant,
            new_quantity=payload.new_quantity,
            movement_type=payload.movement_type,
            reason=payload.reason,
            administrator=admin_user(request),
            reference_number=payload.reference_number,
        )
        con.commit()
        return {"ok": True, **result}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _delta_endpoint(payload: StockDeltaRequest, request: Request, movement_type: str):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        variant = resolve_variant(con, product_id=payload.product_id, variant_id=payload.variant_id, size=payload.size, color=payload.color)
        result = adjust_by_delta(
            con,
            variant=variant,
            delta=-payload.quantity,
            movement_type=movement_type,
            reason=payload.reason,
            administrator=admin_user(request),
            reference_number=payload.reference_number,
            notes=payload.notes,
        )
        con.commit()
        return {"ok": True, **result}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@router.post("/return")
def inventory_return(payload: StockDeltaRequest, request: Request, _=Depends(require_admin)):
    # returns add stock back
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        variant = resolve_variant(con, product_id=payload.product_id, variant_id=payload.variant_id, size=payload.size, color=payload.color)
        result = adjust_by_delta(con, variant=variant, delta=payload.quantity, movement_type="return", reason=payload.reason, administrator=admin_user(request), reference_number=payload.reference_number, notes=payload.notes)
        con.commit()
        return {"ok": True, **result}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@router.post("/damage")
def inventory_damage(payload: StockDeltaRequest, request: Request, _=Depends(require_admin)):
    return _delta_endpoint(payload, request, "damaged_stock")


@router.post("/lost")
def inventory_lost(payload: StockDeltaRequest, request: Request, _=Depends(require_admin)):
    return _delta_endpoint(payload, request, "lost_stock")


@router.put("/variants/{variant_id}")
def inventory_update_variant(variant_id: int, payload: VariantUpdate, request: Request, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        variant = get_variant(con, variant_id)
        data = payload.model_dump(exclude_unset=True)
        reason = data.pop("reason", None) or "Variant updated"
        reference_number = data.pop("reference_number", None) or ""
        new_size = data.get("size", variant["size"])
        new_color = data.get("color", variant["color"])
        new_sku = data.get("variant_sku", variant["variant_sku"])
        from .service import ensure_unique_variant, ensure_unique_barcode
        ensure_unique_variant(con, product_id=variant["product_id"], size=new_size, color=new_color, variant_sku=new_sku, exclude_id=variant_id)
        ensure_unique_barcode(con, data.get("barcode", variant["barcode"]), exclude_id=variant_id)

        stock_change = None
        if "stock_quantity" in data and data["stock_quantity"] is not None and int(data["stock_quantity"]) != int(variant["stock_quantity"]):
            stock_change = int(data["stock_quantity"])
        # update non-stock fields
        fields = []
        params = []
        for k in ["size","color","variant_sku","cost_price","selling_price","barcode","low_stock_threshold","is_active"]:
            if k in data:
                val = data[k]
                if k == "is_active" and val is not None:
                    val = int(bool(val))
                fields.append(f"{k}=?")
                params.append(val)
        if fields:
            params.append(variant_id)
            con.execute(f"UPDATE inventory_variants SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", params)

        variant = get_variant(con, variant_id)
        if stock_change is not None:
            change_variant_stock(con, variant=variant, new_quantity=stock_change, movement_type="manual_correction", reason=reason, administrator=admin_user(request), reference_number=reference_number)
            variant = get_variant(con, variant_id)
        sync_product_stock(con, int(variant["product_id"]))
        con.commit()
        return {"ok": True, "variant": variant}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@router.post("/bulk/variants")
def inventory_bulk_variants(payload: BulkVariantUpdate, request: Request, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        updated = []
        for vid in payload.variant_ids:
            variant = get_variant(con, int(vid))
            fields=[]; params=[]
            if payload.low_stock_threshold is not None: fields.append("low_stock_threshold=?"); params.append(int(payload.low_stock_threshold))
            if payload.is_active is not None: fields.append("is_active=?"); params.append(int(bool(payload.is_active)))
            if payload.cost_price is not None: fields.append("cost_price=?"); params.append(float(payload.cost_price))
            if payload.selling_price is not None: fields.append("selling_price=?"); params.append(float(payload.selling_price))
            if fields:
                params.append(vid)
                con.execute(f"UPDATE inventory_variants SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", params)
            variant = get_variant(con, int(vid))
            if payload.stock_quantity is not None and int(payload.stock_quantity) != int(variant["stock_quantity"]):
                change_variant_stock(con, variant=variant, new_quantity=int(payload.stock_quantity), movement_type="manual_correction", reason=payload.reason, administrator=admin_user(request), reference_number="BULK")
                variant = get_variant(con, int(vid))
            sync_product_stock(con, int(variant["product_id"]))
            updated.append(variant["id"])
        con.commit()
        return {"ok": True, "updated_variant_ids": updated}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@router.post("/bulk/products")
def inventory_bulk_products(payload: BulkProductUpdate, _=Depends(require_admin)):
    con = _main().db()
    try:
        ensure_inventory_schema(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        for pid in payload.product_ids:
            get_variant  # no-op
            prod = con.execute("SELECT id FROM products WHERE id=?", (int(pid),)).fetchone()
            if not prod:
                raise HTTPException(404, f"Product {pid} not found")
            fields=[]; params=[]
            if payload.is_active is not None: fields.append("active=?"); params.append(int(bool(payload.is_active)))
            if payload.category is not None: fields.append("category=?"); params.append(payload.category)
            if payload.brand is not None: fields.append("brand=?"); params.append(payload.brand)
            if payload.supplier is not None: fields.append("supplier=?"); params.append(payload.supplier)
            if payload.low_stock_threshold is not None: fields.append("low_stock_threshold=?"); params.append(int(payload.low_stock_threshold))
            if fields:
                params.append(int(pid))
                con.execute(f"UPDATE products SET {', '.join(fields)} WHERE id=?", params)
            if payload.is_active is not None:
                con.execute("UPDATE inventory_variants SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?", (int(bool(payload.is_active)), int(pid)))
            if payload.low_stock_threshold is not None:
                con.execute("UPDATE inventory_variants SET low_stock_threshold=?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?", (int(payload.low_stock_threshold), int(pid)))
        con.commit()
        return {"ok": True, "updated_product_ids": payload.product_ids}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@router.post("/import")
async def inventory_import(request: Request, file: UploadFile = File(...), apply: bool = False, _=Depends(require_admin)):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(400, "Please upload a CSV file")
    content = (await file.read()).decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    required = {"product_sku","variant_sku","size","color","stock_quantity"}
    cols = {c.strip() for c in (reader.fieldnames or [])}
    missing = [c for c in required if c not in cols]
    if missing:
        raise HTTPException(400, f"Missing required columns: {', '.join(missing)}")

    con = _main().db()
    try:
        ensure_inventory_schema(con)
        migrate_existing_products_to_variants(con)
        con.commit(); con.execute("BEGIN IMMEDIATE")
        preview = []
        errors = []
        seen_variant_skus = set()
        for idx, row in enumerate(reader, start=2):
            variant_sku = (row.get('variant_sku') or '').strip()
            product_sku = (row.get('product_sku') or '').strip()
            size = (row.get('size') or 'Default').strip() or 'Default'
            color = (row.get('color') or 'Default').strip() or 'Default'
            if not variant_sku:
                errors.append(f"Line {idx}: variant_sku is required")
                continue
            if variant_sku.lower() in seen_variant_skus:
                errors.append(f"Line {idx}: duplicate variant_sku in CSV")
                continue
            seen_variant_skus.add(variant_sku.lower())
            try:
                qty_raw = row.get('stock_quantity')
                if qty_raw is None or str(qty_raw).strip() == '':
                    raise ValueError('stock_quantity required')
                qty = int(float(str(qty_raw).strip()))
                if qty < 0: raise ValueError('negative')
            except Exception:
                errors.append(f"Line {idx}: invalid stock_quantity")
                continue
            variant = con.execute("SELECT v.*, p.sku AS product_sku, p.name AS product_name FROM inventory_variants v JOIN products p ON p.id=v.product_id WHERE v.variant_sku=?", (variant_sku,)).fetchone()
            if not variant:
                errors.append(f"Line {idx}: variant_sku not found ({variant_sku})")
                continue
            if product_sku and product_sku != (variant['product_sku'] or ''):
                errors.append(f"Line {idx}: product_sku does not match variant")
                continue
            action = {
                'line': idx,
                'variant_id': variant['id'],
                'product_id': variant['product_id'],
                'product_name': variant['product_name'],
                'variant_sku': variant_sku,
                'from': int(variant['stock_quantity']),
                'to': qty,
                'delta': qty - int(variant['stock_quantity']),
            }
            preview.append(action)
            if apply and action['delta'] != 0:
                change_variant_stock(con, variant=dict(variant), new_quantity=qty, movement_type='manual_correction', reason=(row.get('reason') or 'CSV import').strip() or 'CSV import', administrator=admin_user(request), reference_number=(row.get('reference_number') or file.filename or 'CSV').strip())
            # optional fields
            updates=[]; params=[]
            for field, col in [('low_stock_threshold','low_stock_threshold'),('cost_price','cost_price'),('selling_price','selling_price'),('barcode','barcode')]:
                val = (row.get(col) or '').strip()
                if val == '':
                    continue
                if field in ('low_stock_threshold',):
                    try: parsed=int(float(val))
                    except: errors.append(f"Line {idx}: invalid {col}"); continue
                elif field in ('cost_price','selling_price'):
                    try: parsed=float(val)
                    except: errors.append(f"Line {idx}: invalid {col}"); continue
                else:
                    parsed=val
                updates.append(f"{field}=?"); params.append(parsed)
            is_active_raw = (row.get('is_active') or '').strip().lower()
            if is_active_raw in ('0','1','true','false','yes','no'):
                updates.append('is_active=?'); params.append(1 if is_active_raw in ('1','true','yes') else 0)
            if apply and updates:
                params.append(variant['id'])
                con.execute(f"UPDATE inventory_variants SET {', '.join(updates)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", params)
                sync_product_stock(con, int(variant['product_id']))
        if errors:
            con.rollback()
            return {"ok": False, "applied": False, "errors": errors, "preview": preview}
        if apply:
            con.commit()
        else:
            con.rollback()
        return {"ok": True, "applied": apply, "errors": [], "preview": preview, "count": len(preview)}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
