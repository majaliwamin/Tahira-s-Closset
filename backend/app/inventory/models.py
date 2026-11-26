from __future__ import annotations

import json
import sqlite3
from typing import Iterable


INVENTORY_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS inventory_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    size TEXT NOT NULL DEFAULT 'Default',
    color TEXT NOT NULL DEFAULT 'Default',
    variant_sku TEXT NOT NULL UNIQUE,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    cost_price REAL,
    selling_price REAL,
    barcode TEXT,
    low_stock_threshold INTEGER NOT NULL DEFAULT 3,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_variant_combo ON inventory_variants(product_id, size, color);
CREATE INDEX IF NOT EXISTS idx_inventory_variant_product ON inventory_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_variant_barcode ON inventory_variants(barcode);

CREATE TABLE IF NOT EXISTS inventory_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    variant_id INTEGER,
    movement_type TEXT NOT NULL,
    quantity_change INTEGER NOT NULL,
    quantity_before INTEGER NOT NULL,
    quantity_after INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    administrator TEXT DEFAULT '',
    reference_number TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    supplier TEXT DEFAULT '',
    unit_cost REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY(variant_id) REFERENCES inventory_variants(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_product ON inventory_ledger(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_variant ON inventory_ledger(variant_id);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_created ON inventory_ledger(created_at);
CREATE INDEX IF NOT EXISTS idx_inventory_ledger_type ON inventory_ledger(movement_type);

CREATE TABLE IF NOT EXISTS inventory_migrations (
    key TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _column_names(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _ensure_column(con: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in _column_names(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def ensure_inventory_schema(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(INVENTORY_TABLES_SQL)

    # Extend existing products table non-destructively.
    _ensure_column(con, "products", "brand", "brand TEXT DEFAULT ''")
    _ensure_column(con, "products", "cost_price", "cost_price REAL")
    _ensure_column(con, "products", "low_stock_threshold", "low_stock_threshold INTEGER DEFAULT 3")
    _ensure_column(con, "products", "supplier", "supplier TEXT DEFAULT ''")
    _ensure_column(con, "products", "date_added", "date_added TEXT")
    con.execute("UPDATE products SET date_added = COALESCE(date_added, created_at, CURRENT_TIMESTAMP)")
    con.execute("UPDATE products SET low_stock_threshold = COALESCE(low_stock_threshold, 3)")
    con.execute("UPDATE products SET brand = COALESCE(brand, '')")
    con.execute("UPDATE products SET supplier = COALESCE(supplier, '')")


def _migration_applied(con: sqlite3.Connection, key: str) -> bool:
    row = con.execute("SELECT 1 FROM inventory_migrations WHERE key=?", (key,)).fetchone()
    return row is not None


def _mark_migration(con: sqlite3.Connection, key: str) -> None:
    con.execute(
        "INSERT OR IGNORE INTO inventory_migrations(key, applied_at) VALUES(?, CURRENT_TIMESTAMP)",
        (key,),
    )


def _split_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in str(raw).replace("|", ",").split(",")]
    seen = set()
    out = []
    for p in parts:
        if not p:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _variant_sku(base_sku: str, size: str, color: str, product_id: int, existing: set[str]) -> str:
    base = (base_sku or f"TC-{product_id:04d}").strip().upper().replace(" ", "-")
    s = "".join(ch for ch in size.upper() if ch.isalnum())[:8] or "DEF"
    c = "".join(ch for ch in color.upper() if ch.isalnum())[:8] or "DEF"
    candidate = f"{base}-{s}-{c}"
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{s}-{c}-{suffix}"
        suffix += 1
    existing.add(candidate)
    return candidate


def migrate_existing_products_to_variants(con: sqlite3.Connection, admin_name: str = "system-migration") -> dict:
    ensure_inventory_schema(con)
    key = "inventory_v2_variants_opening_stock"
    if _migration_applied(con, key):
        return {"applied": False, "products_migrated": 0, "variants_created": 0}

    existing_skus = {r[0] for r in con.execute("SELECT variant_sku FROM inventory_variants").fetchall()}
    products = con.execute("SELECT * FROM products ORDER BY id").fetchall()
    products_migrated = 0
    variants_created = 0

    for p in products:
        product_id = p["id"]
        has_variants = con.execute(
            "SELECT 1 FROM inventory_variants WHERE product_id=? LIMIT 1", (product_id,)
        ).fetchone()
        if has_variants:
            continue

        sizes = _split_values(p["sizes"]) or ["Default"]
        colors = _split_values(p["colors"]) or ["Default"]
        total_stock = int(p["stock"] or 0)
        combos = [(s, c) for s in sizes for c in colors]
        # Distribute existing stock to first variant to preserve total without guessing.
        for idx, (size, color) in enumerate(combos):
            qty = total_stock if idx == 0 else 0
            vsku = _variant_sku(p["sku"], size, color, product_id, existing_skus)
            cur = con.execute(
                """
                INSERT INTO inventory_variants(
                    product_id,size,color,variant_sku,stock_quantity,cost_price,selling_price,
                    low_stock_threshold,is_active,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP),CURRENT_TIMESTAMP)
                """,
                (
                    product_id,
                    size,
                    color,
                    vsku,
                    qty,
                    p["cost_price"] if "cost_price" in p.keys() else None,
                    p["sale_price"] if p["sale_price"] is not None else p["price"],
                    int(p["low_stock_threshold"] or 3),
                    int(p["active"] if p["active"] is not None else 1),
                    p["created_at"],
                ),
            )
            variant_id = cur.lastrowid
            variants_created += 1
            con.execute(
                """
                INSERT INTO inventory_ledger(
                    product_id,variant_id,movement_type,quantity_change,quantity_before,quantity_after,
                    reason,administrator,reference_number,notes,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))
                """,
                (
                    product_id,
                    variant_id,
                    "opening_stock",
                    qty,
                    0,
                    qty,
                    "Migrated from legacy product stock",
                    admin_name,
                    f"MIG-P{product_id}-V{variant_id}",
                    "Automatic Inventory 2.0 migration",
                    p["created_at"],
                ),
            )
        products_migrated += 1

    sync_all_product_stocks(con)
    _mark_migration(con, key)
    return {"applied": True, "products_migrated": products_migrated, "variants_created": variants_created}


def sync_product_stock(con: sqlite3.Connection, product_id: int) -> int:
    row = con.execute(
        "SELECT COALESCE(SUM(stock_quantity),0) AS total FROM inventory_variants WHERE product_id=?",
        (product_id,),
    ).fetchone()
    total = int(row["total"] if row else 0)
    con.execute("UPDATE products SET stock=? WHERE id=?", (total, product_id))
    return total


def sync_all_product_stocks(con: sqlite3.Connection) -> None:
    ids = [r[0] for r in con.execute("SELECT id FROM products").fetchall()]
    for pid in ids:
        sync_product_stock(con, pid)
