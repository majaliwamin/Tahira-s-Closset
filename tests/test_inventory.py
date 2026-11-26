import io, csv, sqlite3, json


def login(client):
    r = client.post('/api/login', json={'username':'tahira','password':'Tahira@123'})
    assert r.status_code == 200
    return {'Authorization': f"Bearer {r.json()['token']}"}


def test_migration_preserves_existing_products_and_opening_stock(app_client):
    client, main, work = app_client
    con = sqlite3.connect(work/'data'/'closset.db')
    con.row_factory = sqlite3.Row
    products = con.execute('SELECT * FROM products ORDER BY id').fetchall()
    assert len(products) == 3
    names = [p['name'] for p in products]
    assert 'Classic Black Dress' in names
    # variants created
    variants = con.execute('SELECT * FROM inventory_variants ORDER BY product_id,id').fetchall()
    assert len(variants) >= 3
    # stock preserved: sum variant stock equals original
    for p in products:
        total = con.execute('SELECT COALESCE(SUM(stock_quantity),0) FROM inventory_variants WHERE product_id=?',(p['id'],)).fetchone()[0]
        assert total == p['stock']
    # opening ledger entries
    moves = con.execute("SELECT * FROM inventory_ledger WHERE movement_type='opening_stock'").fetchall()
    assert len(moves) >= 3
    con.close()


def test_dashboard_and_auth(app_client):
    client, *_ = app_client
    r = client.get('/api/inventory/dashboard')
    assert r.status_code == 401
    h = login(client)
    r = client.get('/api/inventory/dashboard', headers=h)
    assert r.status_code == 200
    data = r.json()
    for k in ['total_products','total_active_variants','units_in_stock','out_of_stock_variants','low_stock_variants','inventory_cost_valuation','inventory_selling_valuation','recent_stock_movements','recently_restocked_products']:
        assert k in data
    assert data['total_products'] == 3


def test_variant_creation_matrix_restock_history(app_client):
    client, *_ = app_client
    h = login(client)
    # create product with sizes/colors
    payload = {
        'name':'Matrix Dress','description':'Test','category':'Dresses','brand':'HB','price':10000,'sale_price':9000,'cost_price':5000,
        'sku':'MX-001','stock':2,'sizes':'S,M','colors':'Black,Red','featured':False,'active':True,'low_stock_threshold':2,'supplier':'Test Supplier'
    }
    r = client.post('/api/admin/products', json=payload, headers=h)
    assert r.status_code == 200
    pid = r.json()['id']
    # matrix
    r = client.get(f'/api/inventory/matrix/{pid}', headers=h)
    assert r.status_code == 200
    m = r.json()
    assert set(m['sizes']) == {'S','M'}
    assert set(m['colors']) == {'Black','Red'}
    assert len(m['variants']) == 4
    # find variant S/Black
    v = next(x for x in m['variants'] if x['size']=='S' and x['color']=='Black')
    # restock
    r = client.post('/api/inventory/restock', json={'product_id':pid,'variant_id':v['id'],'quantity_received':5,'supplier':'Acme','cost_price':4500,'reference_number':'INV-1','notes':'Restock'}, headers=h)
    assert r.status_code == 200
    assert r.json()['after'] == v['stock_quantity'] + 5
    # history
    r = client.get(f'/api/inventory/history?product_id={pid}', headers=h)
    assert r.status_code == 200
    items = r.json()['items']
    assert any(i['movement_type']=='restocking' and i['reference_number']=='INV-1' for i in items)


def test_adjust_return_damage_low_out(app_client):
    client, *_ = app_client
    h = login(client)
    # get a variant
    inv = client.get('/api/inventory/variants?limit=10', headers=h).json()['items']
    v = inv[0]
    pid = v['product_id']
    # set known stock
    r = client.put(f"/api/inventory/variants/{v['id']}", json={'stock_quantity':1,'low_stock_threshold':2,'reason':'Set low'}, headers=h)
    assert r.status_code == 200
    low = client.get('/api/inventory/low-stock', headers=h).json()['items']
    assert any(x['id']==v['id'] for x in low)
    # damage to zero
    r = client.post('/api/inventory/damage', json={'product_id':pid,'variant_id':v['id'],'quantity':1,'reason':'Damaged','reference_number':'DMG-1'}, headers=h)
    assert r.status_code == 200
    out = client.get('/api/inventory/out-of-stock', headers=h).json()['items']
    assert any(x['id']==v['id'] for x in out)
    # return adds back
    r = client.post('/api/inventory/return', json={'product_id':pid,'variant_id':v['id'],'quantity':2,'reason':'Returned','reference_number':'RET-1'}, headers=h)
    assert r.status_code == 200
    hist = client.get(f'/api/inventory/history?variant_id={v["id"]}', headers=h).json()['items']
    types = [i['movement_type'] for i in hist]
    assert 'damaged_stock' in types and 'return' in types and 'manual_correction' in types


def test_sku_uniqueness_and_validation(app_client):
    client, *_ = app_client
    h = login(client)
    inv = client.get('/api/inventory/variants?limit=2', headers=h).json()['items']
    a,b = inv[0], inv[1]
    # duplicate sku rejected
    r = client.put(f"/api/inventory/variants/{a['id']}", json={'variant_sku':b['variant_sku'],'reason':'test'}, headers=h)
    assert r.status_code == 409
    # negative stock via normal adjust rejected
    r = client.post('/api/inventory/adjust', json={'product_id':a['product_id'],'variant_id':a['id'],'new_quantity':-1,'reason':'bad','movement_type':'manual_correction'}, headers=h)
    assert r.status_code == 422


def test_csv_export_import_preview(app_client):
    client, *_ = app_client
    h = login(client)
    # export
    r = client.get('/api/inventory/export', headers=h)
    assert r.status_code == 200
    assert 'variant_sku' in r.text
    # build import csv for existing variant
    v = client.get('/api/inventory/variants?limit=1', headers=h).json()['items'][0]
    csv_content = 'product_sku,variant_sku,size,color,stock_quantity,reason,reference_number\n' \
        f"{v['product_sku']},{v['variant_sku']},{v['size']},{v['color']},{v['stock_quantity']+3},CSV import,IMP-1\n"
    files = {'file': ('inv.csv', csv_content, 'text/csv')}
    r = client.post('/api/inventory/import?apply=false', files=files, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True and data['applied'] is False
    assert len(data['preview']) == 1
    # apply
    files = {'file': ('inv.csv', csv_content, 'text/csv')}
    r = client.post('/api/inventory/import?apply=true', files=files, headers=h)
    assert r.status_code == 200
    assert r.json()['applied'] is True
    hist = client.get(f"/api/inventory/history?variant_id={v['id']}", headers=h).json()['items']
    assert any(i['reference_number']=='IMP-1' for i in hist)


def test_public_api_does_not_expose_cost_price(app_client):
    client, *_ = app_client
    r = client.get('/api/products')
    assert r.status_code == 200
    data = r.json()
    assert data
    assert 'cost_price' not in data[0]
    for v in data[0].get('variants',[]):
        assert 'cost_price' not in v
