from __future__ import annotations

import csv
import io
import sqlite3
from typing import Any

from fastapi import HTTPException

from .ledger import record_movement
from .models import sync_product_stock


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def get_product(con: sqlite3.Connection, product_id: int) -> dict:
    row = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)


def get_variant(con: sqlite3.Connection, variant_id: int) -> dict:
    row = con.execute(
        """
        SELECT v.*, p.name AS product_name, p.sku AS product_sku, p.category, p.brand, p.supplier AS product_supplier,
               p.cost_price AS product_cost_price, p.price AS product_price, p.sale_price AS product_sale_price, p.active AS product_active
        FROM inventory_variants v JOIN products p ON p.id=v.product_id WHERE v.id=?
        """,
        (variant_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Variant not found")
    return dict(row)


def resolve_variant(con: sqlite3.Connection, *, product_id: int, variant_id: int | None = None, size: str | None = None, color: str | None = None) -> dict:
    if variant_id:
        v = get_variant(con, variant_id)
        if int(v["product_id"]) != int(product_id):
            raise HTTPException(400, "Variant does not belong to the selected product")
        return v
    size = (size or "Default").strip() or "Default"
    color = (color or "Default").strip() or "Default"
    row = con.execute(
        "SELECT * FROM inventory_variants WHERE product_id=? AND lower(size)=lower(?) AND lower(color)=lower(?)",
        (product_id, size, color),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Variant not found for selected product/size/colour")
    return dict(row)


def ensure_unique_variant(con: sqlite3.Connection, *, product_id: int, size: str, color: str, variant_sku: str, exclude_id: int | None = None):
    params: list[Any] = [product_id, size.lower(), color.lower()]
    sql = "SELECT id FROM inventory_variants WHERE product_id=? AND lower(size)=? AND lower(color)=?"
    if exclude_id:
        sql += " AND id<>?"
        params.append(exclude_id)
    if con.execute(sql, params).fetchone():
        raise HTTPException(409, "A variant with this size and colour already exists for the product")
    params = [variant_sku.strip()]
    sql = "SELECT id FROM inventory_variants WHERE variant_sku=?"
    if exclude_id:
        sql += " AND id<>?"
        params.append(exclude_id)
    if con.execute(sql, params).fetchone():
        raise HTTPException(409, "Variant SKU already exists")
    # barcode uniqueness if provided? not explicitly required, but good to prevent obvious conflicts
    # we only enforce if same barcode assigned to different variant and not empty
    # caller can check barcode separately.


def ensure_unique_barcode(con: sqlite3.Connection, barcode: str | None, exclude_id: int | None = None):
    if not barcode:
        return
    params: list[Any] = [barcode.strip()]
    sql = "SELECT id FROM inventory_variants WHERE barcode=?"
    if exclude_id:
        sql += " AND id<>?"
        params.append(exclude_id)
    if con.execute(sql, params).fetchone():
        raise HTTPException(409, "Barcode already exists")


def list_inventory(
    con: sqlite3.Connection,
    *,
    q: str | None = None,
    category: str | None = None,
    status: str | None = None,
    size: str | None = None,
    color: str | None = None,
    active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    where = []
    params: list[Any] = []
    if q:
        like = f"%{q.strip()}%"
        where.append("(p.name LIKE ? OR p.sku LIKE ? OR v.variant_sku LIKE ? OR IFNULL(v.barcode,'') LIKE ?)")
        params.extend([like, like, like, like])
    if category:
        where.append("p.category=?")
        params.append(category)
    if size:
        where.append("lower(v.size)=lower(?)")
        params.append(size)
    if color:
        where.append("lower(v.color)=lower(?)")
        params.append(color)
    if active is not None:
        where.append("p.active=?")
        params.append(int(active))
    status_sql = {
        "out_of_stock": "v.stock_quantity<=0",
        "low_stock": "v.stock_quantity>0 AND v.stock_quantity<=v.low_stock_threshold",
        "in_stock": "v.stock_quantity>v.low_stock_threshold",
    }
    if status:
        key = status.lower().replace(" ", "_")
        if key not in status_sql:
            raise HTTPException(400, "Invalid stock status filter")
        where.append(status_sql[key])
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    count = con.execute(
        f"""
        SELECT COUNT(DISTINCT p.id)
        FROM products p
        LEFT JOIN inventory_variants v ON v.product_id=p.id
        {where_clause}
        """,
        params,
    ).fetchone()[0]

    product_rows = con.execute(
        f"""
        SELECT p.*,
               COALESCE(SUM(v.stock_quantity),0) AS total_stock,
               COUNT(v.id) AS variant_count,
               SUM(CASE WHEN v.stock_quantity<=0 THEN 1 ELSE 0 END) AS out_of_stock_variants,
               SUM(CASE WHEN v.stock_quantity>0 AND v.stock_quantity<=v.low_stock_threshold THEN 1 ELSE 0 END) AS low_stock_variants
        FROM products p
        LEFT JOIN inventory_variants v ON v.product_id=p.id
        {where_clause}
        GROUP BY p.id
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()

    items = []
    for p in product_rows:
        pid = p["id"]
        variants = con.execute(
            "SELECT * FROM inventory_variants WHERE product_id=? ORDER BY size, color, id", (pid,)
        ).fetchall()
        images = con.execute(
            "SELECT * FROM images WHERE product_id=? ORDER BY primary_image DESC,id", (pid,)
        ).fetchall()
        item = dict(p)
        item["images"] = [dict(i) for i in images]
        item["variants"] = [dict(v) for v in variants]
        item["sizes_list"] = sorted({v["size"] for v in variants})
        item["colors_list"] = sorted({v["color"] for v in variants})
        items.append(item)
    return {"items": items, "total": int(count), "limit": limit, "offset": offset}


def get_matrix(con: sqlite3.Connection, product_id: int) -> dict:
    product = get_product(con, product_id)
    variants = con.execute(
        "SELECT * FROM inventory_variants WHERE product_id=? ORDER BY size,color,id", (product_id,)
    ).fetchall()
    sizes = []
    colors = []
    for v in variants:
        if v["size"] not in sizes: sizes.append(v["size"])
        if v["color"] not in colors: colors.append(v["color"])
    matrix = {}
    for s in sizes:
        matrix[s] = {}
        for c in colors:
            match = next((dict(v) for v in variants if v["size"] == s and v["color"] == c), None)
            matrix[s][c] = match
    return {"product": product, "sizes": sizes, "colors": colors, "matrix": matrix, "variants": [dict(v) for v in variants]}


def _status_for_variant(v: dict) -> str:
    qty = int(v.get("stock_quantity", 0))
    thr = int(v.get("low_stock_threshold", 3))
    if qty <= 0:
        return "OUT_OF_STOCK"
    if qty <= thr:
        return "LOW_STOCK"
    return "IN_STOCK"


def list_variant_rows(con: sqlite3.Connection, *, status: str | None = None, q: str | None = None, limit: int = 200, offset: int = 0) -> dict:
    where = ["1=1"]
    params: list[Any] = []
    if q:
        like = f"%{q.strip()}%"
        where.append("(p.name LIKE ? OR p.sku LIKE ? OR v.variant_sku LIKE ? OR IFNULL(v.barcode,'') LIKE ?)")
        params.extend([like, like, like, like])
    if status:
        s = status.lower().replace(" ", "_")
        if s == "out_of_stock":
            where.append("v.stock_quantity<=0")
        elif s == "low_stock":
            where.append("v.stock_quantity>0 AND v.stock_quantity<=v.low_stock_threshold")
        elif s == "in_stock":
            where.append("v.stock_quantity>v.low_stock_threshold")
        else:
            raise HTTPException(400, "Invalid status")
    where_sql = "WHERE " + " AND ".join(where)
    total = con.execute(
        f"SELECT COUNT(*) FROM inventory_variants v JOIN products p ON p.id=v.product_id {where_sql}", params
    ).fetchone()[0]
    rows = con.execute(
        f"""
        SELECT v.*, p.name AS product_name, p.sku AS product_sku, p.category, p.brand, p.active AS product_active,
               p.cost_price AS product_cost_price, p.price AS product_price, p.sale_price AS product_sale_price
        FROM inventory_variants v JOIN products p ON p.id=v.product_id
        {where_sql}
        ORDER BY CASE WHEN v.stock_quantity<=0 THEN 0 WHEN v.stock_quantity<=v.low_stock_threshold THEN 1 ELSE 2 END,
                 v.stock_quantity ASC, p.name ASC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        d["status"] = _status_for_variant(d)
        items.append(d)
    return {"items": items, "total": int(total), "limit": limit, "offset": offset}


def change_variant_stock(
    con: sqlite3.Connection,
    *,
    variant: dict,
    new_quantity: int,
    movement_type: str,
    reason: str,
    administrator: str,
    reference_number: str = "",
    notes: str = "",
    supplier: str = "",
    unit_cost: float | None = None,
) -> dict:
    if new_quantity < 0:
        raise HTTPException(400, "Stock quantity cannot be negative")
    before = int(variant["stock_quantity"])
    after = int(new_quantity)
    delta = after - before
    if delta == 0 and movement_type != "manual_correction":
        return {"variant_id": variant["id"], "before": before, "after": after, "changed": False}
    con.execute(
        "UPDATE inventory_variants SET stock_quantity=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (after, variant["id"]),
    )
    if supplier:
        con.execute("UPDATE products SET supplier=? WHERE id=?", (supplier, variant["product_id"]))
    if unit_cost is not None:
        con.execute("UPDATE inventory_variants SET cost_price=? WHERE id=?", (unit_cost, variant["id"]))
        con.execute("UPDATE products SET cost_price=COALESCE(cost_price, ?) WHERE id=?", (unit_cost, variant["product_id"]))
    record_movement(
        con,
        product_id=int(variant["product_id"]),
        variant_id=int(variant["id"]),
        movement_type=movement_type,
        quantity_change=delta,
        quantity_before=before,
        quantity_after=after,
        reason=reason,
        administrator=administrator,
        reference_number=reference_number,
        notes=notes,
        supplier=supplier,
        unit_cost=unit_cost,
    )
    sync_product_stock(con, int(variant["product_id"]))
    updated = get_variant(con, int(variant["id"]))
    return {"variant_id": variant["id"], "before": before, "after": after, "changed": True, "variant": updated}


def adjust_by_delta(con: sqlite3.Connection, *, variant: dict, delta: int, movement_type: str, reason: str, administrator: str, reference_number: str = "", notes: str = "", supplier: str = "", unit_cost: float | None = None) -> dict:
    before = int(variant["stock_quantity"])
    after = before + int(delta)
    if after < 0:
        raise HTTPException(400, "Operation would result in negative stock")
    return change_variant_stock(con, variant=variant, new_quantity=after, movement_type=movement_type, reason=reason, administrator=administrator, reference_number=reference_number, notes=notes, supplier=supplier, unit_cost=unit_cost)
