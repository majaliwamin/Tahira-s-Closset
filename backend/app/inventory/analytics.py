from __future__ import annotations

import sqlite3


def dashboard_stats(con: sqlite3.Connection) -> dict:
    total_products = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    active_variants = con.execute("SELECT COUNT(*) FROM inventory_variants WHERE is_active=1").fetchone()[0]
    units_in_stock = con.execute("SELECT COALESCE(SUM(stock_quantity),0) FROM inventory_variants WHERE is_active=1").fetchone()[0]
    out_of_stock = con.execute(
        "SELECT COUNT(*) FROM inventory_variants WHERE is_active=1 AND stock_quantity<=0"
    ).fetchone()[0]
    low_stock = con.execute(
        """
        SELECT COUNT(*) FROM inventory_variants
        WHERE is_active=1 AND stock_quantity>0 AND stock_quantity<=low_stock_threshold
        """
    ).fetchone()[0]
    cost_valuation = con.execute(
        """
        SELECT COALESCE(SUM(COALESCE(v.cost_price, p.cost_price, 0) * v.stock_quantity),0)
        FROM inventory_variants v JOIN products p ON p.id=v.product_id
        WHERE v.is_active=1
        """
    ).fetchone()[0]
    selling_valuation = con.execute(
        """
        SELECT COALESCE(SUM(COALESCE(v.selling_price, p.sale_price, p.price, 0) * v.stock_quantity),0)
        FROM inventory_variants v JOIN products p ON p.id=v.product_id
        WHERE v.is_active=1
        """
    ).fetchone()[0]
    recent_movements = con.execute(
        """
        SELECT l.*, p.name AS product_name, v.variant_sku, v.size, v.color
        FROM inventory_ledger l
        LEFT JOIN products p ON p.id=l.product_id
        LEFT JOIN inventory_variants v ON v.id=l.variant_id
        ORDER BY l.created_at DESC, l.id DESC LIMIT 10
        """
    ).fetchall()
    recently_restocked = con.execute(
        """
        SELECT l.created_at, p.name AS product_name, v.variant_sku, v.size, v.color, l.quantity_change, l.supplier, l.reference_number
        FROM inventory_ledger l
        LEFT JOIN products p ON p.id=l.product_id
        LEFT JOIN inventory_variants v ON v.id=l.variant_id
        WHERE l.movement_type='restocking'
        ORDER BY l.created_at DESC, l.id DESC LIMIT 10
        """
    ).fetchall()
    return {
        "total_products": int(total_products),
        "total_active_variants": int(active_variants),
        "units_in_stock": int(units_in_stock),
        "out_of_stock_variants": int(out_of_stock),
        "low_stock_variants": int(low_stock),
        "inventory_cost_valuation": float(cost_valuation or 0),
        "inventory_selling_valuation": float(selling_valuation or 0),
        "recent_stock_movements": [dict(r) for r in recent_movements],
        "recently_restocked_products": [dict(r) for r in recently_restocked],
    }
