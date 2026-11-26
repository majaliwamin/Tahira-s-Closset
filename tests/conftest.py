import os, shutil, sqlite3, sys, importlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    # Work on a temp copy so tests don't mutate real data
    work = tmp_path / "app"
    shutil.copytree(ROOT / "backend", work / "backend")
    shutil.copytree(ROOT / "frontend", work / "frontend")
    (work / "data").mkdir()
    (work / "uploads" / "products").mkdir(parents=True)
    shutil.copy2(ROOT / "data" / "closset.db", work / "data" / "closset.db")

    monkeypatch.setenv("CLOSSET_ADMIN_USER", "tahira")
    monkeypatch.setenv("CLOSSET_ADMIN_PASSWORD", "Tahira@123")
    monkeypatch.setenv("CLOSSET_TOKEN_SECRET", "test-secret")

    # reload module against temp DB
    for mod in list(sys.modules.keys()):
        if mod == "backend.app.main" or mod.startswith("backend.app.inventory"):
            sys.modules.pop(mod)
    main = importlib.import_module("backend.app.main")
    main.ROOT = work
    main.DATA = work / "data"
    main.UPLOADS = work / "uploads"
    main.DB = work / "data" / "closset.db"
    main.sessions.clear()
    # re-init to ensure migration on copied db
    main.init()
    c = main.db()
    try:
        main.ensure_inventory_schema(c)
        main.migrate_existing_products_to_variants(c)
        main.sync_all_product_stocks(c)
        c.commit()
    finally:
        c.close()
    client = TestClient(main.app)
    return client, main, work
