from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
import sqlite3, os, secrets, hashlib, hmac, shutil, time, json

from backend.app.inventory.router import router as inventory_router
from backend.app.inventory.models import ensure_inventory_schema, migrate_existing_products_to_variants, sync_all_product_stocks, sync_product_stock
from backend.app.inventory.service import get_matrix
from backend.app.inventory.ledger import record_movement

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"data"; UPLOADS=ROOT/"uploads"
DATA.mkdir(exist_ok=True); UPLOADS.mkdir(exist_ok=True)
DB=DATA/"closset.db"
ADMIN_USER=os.getenv("CLOSSET_ADMIN_USER","tahira")
ADMIN_PASSWORD=os.getenv("CLOSSET_ADMIN_PASSWORD","Tahira@123")
TOKEN_SECRET=os.getenv("CLOSSET_TOKEN_SECRET","change-this-secret-in-production")
sessions={}
app=FastAPI(title="Tahira's Closset API",version="2.0.0")

class CacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        p = request.url.path
        if p.startswith('/assets/') or p.startswith('/uploads/'):
            resp.headers['Cache-Control'] = 'public, max-age=86400'
        return resp
app.add_middleware(CacheStaticMiddleware)
app.mount("/uploads",StaticFiles(directory=str(UPLOADS)),name="uploads")
app.mount("/assets",StaticFiles(directory=str(ROOT/"frontend"/"assets")),name="assets")
security=HTTPBearer(auto_error=False)

def db():
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def _col_names(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}

def _ensure_col(con, table, name, ddl):
    if name not in _col_names(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

def init():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT DEFAULT '',category TEXT DEFAULT 'Uncategorized',price REAL NOT NULL DEFAULT 0,sale_price REAL,sku TEXT,stock INTEGER NOT NULL DEFAULT 0,sizes TEXT DEFAULT '',colors TEXT DEFAULT '',featured INTEGER DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS images(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,path TEXT,primary_image INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS enquiries(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,contact TEXT,product_id INTEGER,message TEXT,status TEXT DEFAULT 'new',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,customer TEXT,contact TEXT,location TEXT DEFAULT '',note TEXT DEFAULT '',items TEXT,total REAL,status TEXT DEFAULT 'pending',source TEXT DEFAULT 'web',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    # extend legacy products for inventory 2.0
    _ensure_col(c,'products','brand',"brand TEXT DEFAULT ''")
    _ensure_col(c,'products','cost_price',"cost_price REAL")
    _ensure_col(c,'products','low_stock_threshold',"low_stock_threshold INTEGER DEFAULT 3")
    _ensure_col(c,'products','supplier',"supplier TEXT DEFAULT ''")
    _ensure_col(c,'products','date_added',"date_added TEXT")
    c.execute("UPDATE products SET date_added=COALESCE(date_added,created_at,CURRENT_TIMESTAMP)")
    c.execute("UPDATE products SET low_stock_threshold=COALESCE(low_stock_threshold,3)")
    c.execute("UPDATE products SET brand=COALESCE(brand,'')")
    c.execute("UPDATE products SET supplier=COALESCE(supplier,'')")
    if c.execute("SELECT count(*) FROM products").fetchone()[0]==0:
        sample=[("Classic Black Dress","A timeless piece for elegant occasions.","Dresses",45000,None,"TC-001",5,"S,M,L,XL","Black",1,1,"",None,3,"",""),("Soft Knit Set","Comfortable everyday style.","Sets",38000,None,"TC-002",8,"S,M,L","Cream,Beige",0,1,"",None,3,"",""),("Floral Summer Dress","Lightweight floral styling.","Dresses",32000,28000,"TC-003",4,"S,M,L,XL","Pink,Blue",1,1,"",None,3,"","")]
        c.executemany("INSERT INTO products(name,description,category,price,sale_price,sku,stock,sizes,colors,featured,active,brand,cost_price,low_stock_threshold,supplier,date_added) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",sample)
    c.commit(); c.close()

init()
try:
    _c=db()
    try:
        ensure_inventory_schema(_c)
        migrate_existing_products_to_variants(_c)
        sync_all_product_stocks(_c)
        _c.commit()
    finally:
        _c.close()
except Exception as _e:
    print('Inventory migration warning:', _e)

app.include_router(inventory_router)

def get_admin(creds:HTTPAuthorizationCredentials=Depends(security)):
    if not creds or creds.scheme.lower()!="bearer" or creds.credentials not in sessions:
        raise HTTPException(401,"Administrator sign-in required")
    return True

class Product(BaseModel):
    name:str
    description:str=""
    category:str="Uncategorized"
    brand:str=""
    price:float=Field(ge=0)
    sale_price:Optional[float]=None
    cost_price:Optional[float]=Field(default=None, ge=0)
    sku:str=""
    stock:int=Field(default=0,ge=0)
    sizes:str=""
    colors:str=""
    featured:bool=False
    active:bool=True
    low_stock_threshold:int=Field(default=3, ge=0)
    supplier:str=""
    date_added:Optional[str]=None

class Login(BaseModel):
    username:str
    password:str
class Enquiry(BaseModel):
    name:str
    contact:str=""
    product_id:Optional[int]=None
    message:str

def row_product(r, include_private=False):
    p=dict(r)
    if not include_private:
        p.pop('cost_price', None)
    p["images"]=[]
    return p

def _attach_inventory(con, p, include_private=False):
    p["images"]=[dict(i) for i in con.execute("SELECT * FROM images WHERE product_id=? ORDER BY primary_image DESC,id",(p["id"],)).fetchall()]
    try:
        vars_rows = con.execute("SELECT * FROM inventory_variants WHERE product_id=? ORDER BY size,color,id",(p["id"],)).fetchall()
        p["variants"] = []
        for v in vars_rows:
            vd=dict(v)
            if not include_private:
                vd.pop('cost_price', None)
            vd['status'] = 'OUT_OF_STOCK' if vd['stock_quantity']<=0 else ('LOW_STOCK' if vd['stock_quantity']<=vd['low_stock_threshold'] else 'IN_STOCK')
            p["variants"].append(vd)
        p["stock"] = sum(int(v['stock_quantity']) for v in p['variants']) if p['variants'] else int(p.get('stock') or 0)
        p["sizes_list"] = sorted({v['size'] for v in p['variants']})
        p["colors_list"] = sorted({v['color'] for v in p['variants']})
    except Exception:
        p.setdefault('variants',[])
        p.setdefault('sizes_list',[])
        p.setdefault('colors_list',[])
    return p

def get_products(active_only=False, include_private=False):
    c=db()
    try:
        ensure_inventory_schema(c)
        _ensure_col(c, "orders", "location", "location TEXT DEFAULT ''")
        _ensure_col(c, "orders", "note", "note TEXT DEFAULT ''")
        _ensure_col(c, "orders", "source", "source TEXT DEFAULT 'web'")
        migrate_existing_products_to_variants(c)
        rows=c.execute("SELECT * FROM products"+(" WHERE active=1" if active_only else "")+" ORDER BY created_at DESC").fetchall()
        out=[]
        for r in rows:
            p=row_product(r, include_private=include_private)
            out.append(_attach_inventory(c,p,include_private=include_private))
        return out
    finally:
        c.close()

def _audit(con, action, detail):
    con.execute("INSERT INTO audit(action,detail,created_at) VALUES(?,?,CURRENT_TIMESTAMP)",(action, detail))

@app.get("/api/health")
def health(): return {"status":"ok","service":"Tahira's Closset","version":"2.0.0"}

@app.get("/api/products")
def products(category:Optional[str]=None,q:Optional[str]=None,featured:Optional[bool]=None):
    data=get_products(True, include_private=False)
    if category: data=[p for p in data if (p.get("category") or "").lower()==category.lower()]
    if q:
        ql=q.lower()
        data=[p for p in data if ql in (str(p.get("name",""))+" "+str(p.get("description",""))+" "+str(p.get("category",""))+" "+str(p.get("sku",""))).lower() or any(ql in str(v.get('variant_sku','')).lower() for v in p.get('variants',[]))]
    if featured is not None: data=[p for p in data if bool(p["featured"])==featured]
    # Public: do not expose cost/profit/private inventory admin fields beyond what's needed
    for p in data:
        p.pop('cost_price', None)
        p.pop('supplier', None)
        for v in p.get('variants',[]):
            v.pop('cost_price', None)
    return data

@app.get("/api/products/{pid}")
def product_detail(pid:int):
    data=get_products(True, include_private=False)
    for p in data:
        if int(p['id'])==int(pid):
            p.pop('cost_price',None); p.pop('supplier',None)
            for v in p.get('variants',[]): v.pop('cost_price',None)
            return p
    raise HTTPException(404,"Product not found")

@app.get("/api/categories")
def categories():
    c=db(); vals=c.execute("SELECT DISTINCT category FROM products WHERE active=1 ORDER BY category").fetchall(); c.close()
    return [v[0] for v in vals]

@app.post("/api/login")
def login(payload:Login):
    if not hmac.compare_digest(payload.username,ADMIN_USER) or not hmac.compare_digest(payload.password,ADMIN_PASSWORD):
        raise HTTPException(401,"Incorrect username or password")
    token=secrets.token_urlsafe(32); sessions[token]=time.time()
    return {"token":token,"username":ADMIN_USER}

@app.post("/api/logout",dependencies=[Depends(get_admin)])
def logout(creds:HTTPAuthorizationCredentials=Depends(security)):
    sessions.pop(creds.credentials,None); return {"ok":True}

@app.get("/api/admin/dashboard",dependencies=[Depends(get_admin)])
def dashboard():
    c=db()
    try:
        ensure_inventory_schema(c); migrate_existing_products_to_variants(c)
        counts={"products":c.execute("SELECT count(*) FROM products").fetchone()[0],
        "available":c.execute("SELECT count(*) FROM products WHERE stock>0 AND active=1").fetchone()[0],
        "low_stock":c.execute("SELECT COUNT(*) FROM inventory_variants WHERE is_active=1 AND stock_quantity>0 AND stock_quantity<=low_stock_threshold").fetchone()[0],
        "out_of_stock":c.execute("SELECT COUNT(*) FROM inventory_variants WHERE is_active=1 AND stock_quantity<=0").fetchone()[0],
        "enquiries":c.execute("SELECT count(*) FROM enquiries").fetchone()[0],
        "new_enquiries":c.execute("SELECT count(*) FROM enquiries WHERE status='new'").fetchone()[0],
        "orders":c.execute("SELECT count(*) FROM orders").fetchone()[0],
        "pending_orders":c.execute("SELECT count(*) FROM orders WHERE status='pending'").fetchone()[0]}
        return counts
    finally:
        c.close()

def _normalize_variants_payload(p:Product, product_id:int, existing_variants:list[dict]|None=None):
    sizes=[s.strip() for s in (p.sizes or '').replace('|',',').split(',') if s.strip()]
    colors=[s.strip() for s in (p.colors or '').replace('|',',').split(',') if s.strip()]
    if not sizes: sizes=['Default']
    if not colors: colors=['Default']
    # de-dupe preserving order
    def dedupe(arr):
        seen=set(); out=[]
        for x in arr:
            k=x.lower()
            if k in seen: continue
            seen.add(k); out.append(x)
        return out
    sizes=dedupe(sizes); colors=dedupe(colors)
    existing_by_combo = {(v['size'].lower(), v['color'].lower()): v for v in (existing_variants or [])}
    combos=[]
    for s in sizes:
        for col in colors:
            combos.append((s,col))
    out=[]
    used_skus={v['variant_sku'] for v in (existing_variants or [])}
    base=(p.sku or f'TC-{product_id:04d}').strip().upper().replace(' ','-') or f'TC-{product_id:04d}'
    total=int(p.stock or 0)
    for idx,(s,col) in enumerate(combos):
        key=(s.lower(),col.lower())
        prev=existing_by_combo.get(key)
        if prev:
            out.append({**prev,'size':s,'color':col,'is_active':int(p.active)})
            continue
        s_code=''.join(ch for ch in s.upper() if ch.isalnum())[:8] or 'DEF'
        c_code=''.join(ch for ch in col.upper() if ch.isalnum())[:8] or 'DEF'
        vsku=f"{base}-{s_code}-{c_code}"
        n=2
        while vsku in used_skus:
            vsku=f"{base}-{s_code}-{c_code}-{n}"; n+=1
        used_skus.add(vsku)
        qty=total if idx==0 and not existing_variants else 0
        out.append({'size':s,'color':col,'variant_sku':vsku,'stock_quantity':qty,'cost_price':p.cost_price,'selling_price':p.sale_price if p.sale_price is not None else p.price,'barcode':None,'low_stock_threshold':int(p.low_stock_threshold or 3),'is_active':int(p.active)})
    return out

@app.post("/api/admin/products",dependencies=[Depends(get_admin)])
def create_product(p:Product, request: Request):
    c=db()
    try:
        ensure_inventory_schema(c); migrate_existing_products_to_variants(c)
        c.commit(); c.execute("BEGIN IMMEDIATE")
        cur=c.execute("INSERT INTO products(name,description,category,brand,price,sale_price,cost_price,sku,stock,sizes,colors,featured,active,low_stock_threshold,supplier,date_added) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))",(p.name,p.description,p.category,p.brand,p.price,p.sale_price,p.cost_price,p.sku,0,p.sizes,p.colors,int(p.featured),int(p.active),int(p.low_stock_threshold),p.supplier,p.date_added))
        pid=cur.lastrowid
        variants=_normalize_variants_payload(p,pid,[])
        for v in variants:
            c.execute("""INSERT INTO inventory_variants(product_id,size,color,variant_sku,stock_quantity,cost_price,selling_price,barcode,low_stock_threshold,is_active,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
                      (pid,v['size'],v['color'],v['variant_sku'],int(v['stock_quantity']),v.get('cost_price'),v.get('selling_price'),v.get('barcode'),int(v.get('low_stock_threshold',3)),int(v.get('is_active',1))))
            vid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
            record_movement(c, product_id=pid, variant_id=vid, movement_type='opening_stock', quantity_change=int(v['stock_quantity']), quantity_before=0, quantity_after=int(v['stock_quantity']), reason='Initial stock on product creation', administrator=ADMIN_USER, reference_number=f'PROD-{pid}')
        sync_product_stock(c,pid)
        _audit(c,"product_created",p.name)
        c.commit()
        return {"id":pid}
    except Exception:
        c.rollback(); raise
    finally:
        c.close()

@app.put("/api/admin/products/{pid}",dependencies=[Depends(get_admin)])
def update_product(pid:int,p:Product):
    c=db()
    try:
        ensure_inventory_schema(c); migrate_existing_products_to_variants(c)
        exists=c.execute("SELECT id FROM products WHERE id=?",(pid,)).fetchone()
        if not exists: raise HTTPException(404,"Product not found")
        c.commit(); c.execute("BEGIN IMMEDIATE")
        c.execute("""UPDATE products SET name=?,description=?,category=?,brand=?,price=?,sale_price=?,cost_price=?,sku=?,sizes=?,colors=?,featured=?,active=?,low_stock_threshold=?,supplier=?,date_added=COALESCE(?,date_added) WHERE id=?""",
                  (p.name,p.description,p.category,p.brand,p.price,p.sale_price,p.cost_price,p.sku,p.sizes,p.colors,int(p.featured),int(p.active),int(p.low_stock_threshold),p.supplier,p.date_added,pid))
        existing=[dict(r) for r in c.execute("SELECT * FROM inventory_variants WHERE product_id=?",(pid,)).fetchall()]
        desired=_normalize_variants_payload(p,pid,existing)
        desired_keys={(v['size'].lower(),v['color'].lower()) for v in desired}
        for v in desired:
            prev=next((e for e in existing if e['size'].lower()==v['size'].lower() and e['color'].lower()==v['color'].lower()),None)
            if prev:
                c.execute("""UPDATE inventory_variants SET size=?,color=?,variant_sku=?,cost_price=?,selling_price=?,low_stock_threshold=?,is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                          (v['size'],v['color'],v.get('variant_sku',prev['variant_sku']),p.cost_price if p.cost_price is not None else prev.get('cost_price'), p.sale_price if p.sale_price is not None else p.price, int(p.low_stock_threshold or prev.get('low_stock_threshold',3)), int(p.active), prev['id']))
            else:
                c.execute("""INSERT INTO inventory_variants(product_id,size,color,variant_sku,stock_quantity,cost_price,selling_price,barcode,low_stock_threshold,is_active,created_at,updated_at)
                             VALUES(?,?,?,?,0,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
                          (pid,v['size'],v['color'],v['variant_sku'],p.cost_price,p.sale_price if p.sale_price is not None else p.price,None,int(p.low_stock_threshold or 3),int(p.active)))
                vid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
                record_movement(c, product_id=pid, variant_id=vid, movement_type='opening_stock', quantity_change=0, quantity_before=0, quantity_after=0, reason='Variant created from product update', administrator=ADMIN_USER, reference_number=f'PROD-{pid}')
        # deactivate removed combos with zero stock; keep stocked removed combos to avoid data loss
        for e in existing:
            key=(e['size'].lower(),e['color'].lower())
            if key not in desired_keys:
                if int(e['stock_quantity'])==0:
                    c.execute("UPDATE inventory_variants SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (e['id'],))
                else:
                    c.execute("UPDATE inventory_variants SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (e['id'],))
                    record_movement(c, product_id=pid, variant_id=e['id'], movement_type='manual_correction', quantity_change=0, quantity_before=int(e['stock_quantity']), quantity_after=int(e['stock_quantity']), reason='Variant removed from product options; deactivated with stock retained', administrator=ADMIN_USER, reference_number=f'PROD-{pid}')
        sync_product_stock(c,pid)
        _audit(c,"product_updated",p.name)
        c.commit(); return {"ok":True}
    except Exception:
        c.rollback(); raise
    finally:
        c.close()

@app.delete("/api/admin/products/{pid}",dependencies=[Depends(get_admin)])
def delete_product(pid:int):
    c=db()
    try:
        c.commit(); c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM images WHERE product_id=?",(pid,))
        c.execute("DELETE FROM inventory_ledger WHERE product_id=?",(pid,))
        c.execute("DELETE FROM inventory_variants WHERE product_id=?",(pid,))
        c.execute("DELETE FROM products WHERE id=?",(pid,))
        _audit(c,'product_deleted', str(pid))
        c.commit();return {"ok":True}
    except Exception:
        c.rollback(); raise
    finally:
        c.close()

@app.post("/api/admin/products/{pid}/images",dependencies=[Depends(get_admin)])
async def upload_image(pid:int,file:UploadFile=File(...)):
    if not file.content_type or not file.content_type.startswith("image/"): raise HTTPException(400,"Please upload an image file.")
    ext=Path(file.filename or "image").suffix.lower()
    if ext not in [".jpg",".jpeg",".png",".webp",".gif"]: raise HTTPException(400,"Supported image formats: JPG, PNG, WEBP, GIF")
    content=await file.read()
    if len(content)>8*1024*1024: raise HTTPException(413,"Image must be smaller than 8 MB")
    c=db()
    try:
        exists=c.execute("SELECT id FROM products WHERE id=?",(pid,)).fetchone()
        if not exists: raise HTTPException(404,"Product not found")
        folder=UPLOADS/"products";folder.mkdir(exist_ok=True); fname=f"{pid}-{secrets.token_hex(8)}{ext}"
        with open(folder/fname,"wb") as f:f.write(content)
        path=f"/uploads/products/{fname}"
        cur=c.execute("SELECT count(*) FROM images WHERE product_id=?",(pid,)).fetchone()[0]
        c.execute("INSERT INTO images(product_id,path,primary_image) VALUES(?,?,?)",(pid,path,int(cur==0)));c.commit()
        return {"path":path}
    finally:
        c.close()

@app.delete("/api/admin/images/{iid}",dependencies=[Depends(get_admin)])
def delete_image(iid:int):
    c=db()
    try:
        r=c.execute("SELECT * FROM images WHERE id=?",(iid,)).fetchone()
        if not r: raise HTTPException(404,"Image not found")
        try:
            fp=ROOT/r["path"].lstrip("/")
            if fp.exists():fp.unlink()
        except:pass
        c.execute("DELETE FROM images WHERE id=?",(iid,));c.commit();return {"ok":True}
    finally:
        c.close()

@app.post("/api/enquiries")
def enquiry(e:Enquiry):
    if not e.name.strip() or not e.message.strip():raise HTTPException(400,"Name and message required")
    c=db();
    try:
        cur=c.execute("INSERT INTO enquiries(name,contact,product_id,message) VALUES(?,?,?,?)",(e.name,e.contact,e.product_id,e.message));c.commit();return {"id":cur.lastrowid}
    finally:
        c.close()

@app.get("/api/admin/enquiries",dependencies=[Depends(get_admin)])
def admin_enquiries():
    c=db();rows=c.execute("SELECT e.*,p.name product_name FROM enquiries e LEFT JOIN products p ON p.id=e.product_id ORDER BY e.created_at DESC").fetchall();c.close();return [dict(r) for r in rows]

@app.patch("/api/admin/enquiries/{eid}",dependencies=[Depends(get_admin)])
def change_enquiry(eid:int,status:str):
    if status not in ("new","read","replied","resolved","archived"):raise HTTPException(400,"Invalid status")
    c=db();c.execute("UPDATE enquiries SET status=? WHERE id=?",(status,eid));c.commit();c.close();return {"ok":True}

@app.delete("/api/admin/enquiries/{eid}",dependencies=[Depends(get_admin)])
def delete_enquiry(eid:int):
    c=db();c.execute("DELETE FROM enquiries WHERE id=?",(eid,));c.commit();c.close();return {"ok":True}

@app.post("/api/orders")
def create_order(payload:dict):
    if not payload.get("customer") or not payload.get("contact") or not payload.get("items"):raise HTTPException(400,"Please complete your order details")
    c=db()
    try:
        cur=c.execute("INSERT INTO orders(customer,contact,items,total) VALUES(?,?,?,?)",(payload["customer"],payload["contact"],json.dumps(payload["items"]),float(payload.get("total",0))));c.commit();return {"id":cur.lastrowid,"status":"pending"}
    finally:
        c.close()

@app.get("/api/admin/orders",dependencies=[Depends(get_admin)])
def admin_orders():
    c=db(); rows=c.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall();c.close();return [dict(r) for r in rows]

@app.patch("/api/admin/orders/{oid}",dependencies=[Depends(get_admin)])
def update_order(oid:int,status:str):
    allowed=["pending","confirmed","paid","processing","ready for collection","dispatched","delivered","cancelled"]
    if status not in allowed:raise HTTPException(400,"Invalid status")
    c=db();c.execute("UPDATE orders SET status=? WHERE id=?",(status,oid));c.commit();c.close();return {"ok":True}

@app.get("/api/settings")
def settings():
    c=db(); rows=c.execute("SELECT key,value FROM settings").fetchall(); c.close();out={r["key"]:r["value"] for r in rows}
    out.setdefault("closset_name","TAHIRA'S CLOSSET")
    out.setdefault("tagline","Wear Your Style. Discover Your Elegance.")
    out.setdefault("whatsapp","https://chat.whatsapp.com/KKDXAzRiifw4FSNPM8qskX?s=sw&p=a&mlu=4&ilr=4&iam=2")
    out.setdefault("currency","MK")
    out.setdefault("contact","+265 893 312 761")
    out.setdefault("location","Tahira's Closset, Nkhotakota Boma District, Malawi")
    out.setdefault("map_url","https://www.google.com/maps/search/?api=1&query=Tahira%27s+Closset+Nkhotakota+Boma+District+Lake+Malawi")
    out.setdefault("delivery","")
    out.setdefault("hero_phrases","Kodi inu zabwino ai?\nKodi mungakonde kuyesa chovala chanji lero?\nKodi mukufuna saizi yanji?\nKodi mukukonda mtundu wanji?\nKodi mukufuna zovala za mwambo uti?\nKodi tingakuthandizeni kusankha zovala?\nKodi mukufuna kuoneka motani lero?\nKodi mwayesa kale kalembedwe kameneka?\nKodi mukufuna kuti tikutumizireni zithunzi zina?\nKodi mukufuna kugula tsopano kapena mufunsa kaye?\nKodi mukufuna zovala za tsiku lapadera?\nTakulandirani ku Tahira's Closset.\nNdife okondwa kukuonani pano.\nMutha kusankha zomwe mukuzikonda.\nTili pano kukuthandizani nthawi iliyonse.\nValani zomwe zimakupatsani chidaliro.\nKhalani omasuka kutifunsa mafunso.\nTili ndi zovala zokongola kwa inu.\nSankhani kalembedwe komwe kakugwirizana nanu.\nTitha kukuthandizani kupeza saizi yoyenera.\nLumikizanani nafe pa WhatsApp mosavuta.\nTikuyankhani mwachangu momwe tingathere.\nOnani zatsopano zomwe zalowa lero.\nZovala zathu zasankhidwa mosamala.\nMutha kutitumizira uthenga nthawi iliyonse.\nTikukuthokozani chifukwa chotichezera.\nKhalani ndi tsiku labwino komanso lokongola.\nTiyeni tikuthandizeni kupeza zomwe mukufuna.\nMtundu uliwonse ukusonyeza umunthu wanu.\nTimayamikira kukoma kwanu.\nTikufunirani zabwino pamene mukusankha.")
    return out

@app.put("/api/admin/settings",dependencies=[Depends(get_admin)])
def save_settings(payload:dict):
    c=db()
    try:
        for k,v in payload.items():c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(k),str(v)))
        c.commit();return {"ok":True}
    finally:
        c.close()

@app.get("/api/admin/audit",dependencies=[Depends(get_admin)])
def audit():
    c=db();rows=c.execute("SELECT * FROM audit ORDER BY created_at DESC LIMIT 100").fetchall();c.close();return [dict(r) for r in rows]

@app.get("/api/admin/products",dependencies=[Depends(get_admin)])
def admin_products():
    return get_products(False, include_private=True)

@app.get("/",response_class=HTMLResponse)
def home():return FileResponse(ROOT/"frontend"/"index.html")
@app.get("/{page}",response_class=HTMLResponse)
def page(page:str):
    if page in ["shop","admin","login","product","about","contact"]:return FileResponse(ROOT/"frontend"/f"{page}.html")
    raise HTTPException(404,"Page not found")
