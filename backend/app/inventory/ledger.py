from __future__ import annotations

import sqlite3
from typing import Any


MOVEMENT_TYPES = {
    "opening_stock",
    "restocking",
    "sale",
    "reservation",
    "reservation_release",
    "return",
    "damaged_stock",
    "lost_stock",
    "manual_correction",
    "stock_transfer",
}


def record_movement(
    con: sqlite3.Connection,
    *,
    product_id: int,
    variant_id: int | None,
    movement_type: str,
    quantity_change: int,
    quantity_before: int,
    quantity_after: int,
    reason: str = "",
    administrator: str = "",
    reference_number: str = "",
    notes: str = "",
    supplier: str = "",
    unit_cost: float | None = None,
) -> int:
    if movement_type not in MOVEMENT_TYPES:
        raise ValueError(f"Invalid movement type: {movement_type}")
    cur = con.execute(
        """
        INSERT INTO inventory_ledger(
            product_id, variant_id, movement_type, quantity_change, quantity_before, quantity_after,
            reason, administrator, reference_number, notes, supplier, unit_cost, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        """,
        (
            product_id,
            variant_id,
            movement_type,
            int(quantity_change),
            int(quantity_before),
            int(quantity_after),
            reason or "",
            administrator or "",
            reference_number or "",
            notes or "",
            supplier or "",
            unit_cost,
        ),
    )
    return int(cur.lastrowid)


def list_movements(
    con: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    product_id: int | None = None,
    variant_id: int | None = None,
    movement_type: str | None = None,
    sku: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where = []
    params: list[Any] = []
    if product_id:
        where.append("l.product_id=?")
        params.append(product_id)
    if variant_id:
        where.append("l.variant_id=?")
        params.append(variant_id)
    if movement_type:
        where.append("l.movement_type=?")
        params.append(movement_type)
    if sku:
        where.append("(p.sku LIKE ? OR v.variant_sku LIKE ? OR v.barcode LIKE ?)")
        like = f"%{sku}%"
        params.extend([like, like, like])
    if date_from:
        where.append("date(l.created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(l.created_at) <= date(?)")
        params.append(date_to)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    base = f"""
        FROM inventory_ledger l
        LEFT JOIN products p ON p.id=l.product_id
        LEFT JOIN inventory_variants v ON v.id=l.variant_id
        {where_sql}
    """
    total = con.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    rows = con.execute(
        f"""
        SELECT l.*, p.name AS product_name, p.sku AS product_sku, p.category,
               v.variant_sku, v.size, v.color, v.barcode
        {base}
        ORDER BY l.created_at DESC, l.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    return [dict(r) for r in rows], int(total)
