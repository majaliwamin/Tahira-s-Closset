const API="/api";let cart=JSON.parse(localStorage.getItem("tc_cart")||"[]");let token=localStorage.getItem("tc_token");let currentProducts=[];let uploadFiles=[];let adminInventory=[];let selectedVariants=new Set();let importPreviewRows=[];
function money(v){let s=Number(v||0).toLocaleString();return `${(window.currency||"MK")} ${s}`}
function toast(msg){let t=document.createElement("div");t.className="toast";t.setAttribute("role","status");t.setAttribute("aria-live","polite");t.textContent=msg;document.body.append(t);setTimeout(()=>t.remove(),3200)}
function esc(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))}
async function api(path,opts={}){let h=opts.headers||{};if(token)h["Authorization"]="Bearer "+token;if(opts.body&&!(opts.body instanceof FormData))h["Content-Type"]="application/json";let r=await fetch(API+path,{...opts,headers:h});if(!r.ok){let m="Request failed";try{let j=await r.json();m=j.detail||j.message||JSON.stringify(j)}catch{try{m=await r.text()}catch{}}throw Error(m||"Request failed")}if(r.status===204)return null;const ct=r.headers.get('content-type')||'';if(ct.includes('application/json'))return r.json();return r.text()}
function img(p){let i=p.images?.[0]?.path;return i?`<img loading="lazy" src="${i}" alt="${esc(p.name)}">`:`<div class="placeholder">${esc((p.name||'H').slice(0,1))}</div>`}
function stockStatus(v){let q=Number(v.stock_quantity??v.stock??0),t=Number(v.low_stock_threshold??3);if(q<=0)return 'OUT_OF_STOCK'; if(q<=t)return 'LOW_STOCK'; return 'IN_STOCK'}
function statusBadge(s){let map={IN_STOCK:['In stock','ok'],LOW_STOCK:['Low stock','warn'],OUT_OF_STOCK:['Out of stock','bad']};let [l,c]=map[s]||[s,''];return `<span class="badge ${c}">${l}</span>`}

const THEMES=['default','dark','green','purple-blue','red'];
function applyTheme(theme){const t=theme||localStorage.getItem('tc_theme')||'default';document.documentElement.setAttribute('data-theme',t);localStorage.setItem('tc_theme',t);const btn=document.getElementById('theme-toggle'); if(btn){btn.title='Theme: '+t; btn.setAttribute('aria-label','Change theme (current: '+t+')');}}
document.addEventListener("DOMContentLoaded",async()=>{
  applyTheme();
  document.getElementById('theme-toggle')?.addEventListener('click',()=>{const cur=localStorage.getItem('tc_theme')||'default'; const i=THEMES.indexOf(cur); applyTheme(THEMES[(i+1)%THEMES.length]);});
  document.getElementById("hamb")?.addEventListener("click",()=>document.getElementById("nav")?.classList.toggle("show"));
  document.getElementById("year")&&(document.getElementById("year").textContent=new Date().getFullYear());
  initHeroSlider();
  initHomeTabs();
  document.querySelectorAll('.nav-link[data-section]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();showSection(a.dataset.section)}));
  if(document.getElementById("featured"))loadFeatured();
  if(document.getElementById("shop-grid"))loadShop();
  if(document.getElementById("login-form"))loginSetup();
  if(document.getElementById("metrics"))initAdmin();
  if(document.getElementById("product-detail"))loadDetail();
  document.getElementById("product-form")?.addEventListener("submit",saveProduct);
  document.getElementById("product-images")?.addEventListener("change",previewFiles);
  document.getElementById("settings-form")?.addEventListener("submit",saveSettings);
  document.getElementById("phrases-form")?.addEventListener("submit",savePhrases);
  document.getElementById("add-phrase-btn")?.addEventListener("click",()=>{const ta=document.getElementById("hero_phrases_input"); if(!ta) return; ta.value = (ta.value?ta.value.replace(/\s*$/,"\n"):"") + "New market phrase..."; ta.focus(); ta.scrollTop=ta.scrollHeight;});
  document.getElementById("restock-form")?.addEventListener("submit",submitRestock);
  document.getElementById("variant-form")?.addEventListener("submit",saveVariant);
  updateCartCount();
});

let _heroTimer=null;
function initHeroSlider(){
  const slides=[...document.querySelectorAll('.hero-slide')];
  const reduce=window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(slides.length>1 && !reduce){
    if(_heroTimer) clearInterval(_heroTimer);
    let i=slides.findIndex(s=>s.classList.contains('active'));
    if(i<0) i=0;
    slides.forEach((s,idx)=>s.classList.toggle('active', idx===i));
    _heroTimer=setInterval(()=>{
      if(!slides[i]) i=0;
      slides[i].classList.remove('active');
      i=(i+1)%slides.length;
      slides[i].classList.add('active');
    },3500);
  }
  initChichewaRotator(reduce);
}

async function initChichewaRotator(reduce){
  const el=document.getElementById('chichewa-text');
  if(!el) return;
  let lines=["Kodi inu zabwino ai?","Kodi mungakonde kuyesa chovala chanji lero?","Kodi mukufuna saizi yanji?","Kodi mukukonda mtundu wanji?","Kodi mukufuna zovala za mwambo uti?","Kodi tingakuthandizeni kusankha zovala?","Kodi mukufuna kuoneka motani lero?","Kodi mwayesa kale kalembedwe kameneka?","Kodi mukufuna kuti tikutumizireni zithunzi zina?","Kodi mukufuna kugula tsopano kapena mufunsa kaye?","Kodi mukufuna zovala za tsiku lapadera?","Takulandirani ku Tahira's Closset.","Ndife okondwa kukuonani pano.","Mutha kusankha zomwe mukuzikonda.","Tili pano kukuthandizani nthawi iliyonse.","Valani zomwe zimakupatsani chidaliro.","Khalani omasuka kutifunsa mafunso.","Tili ndi zovala zokongola kwa inu.","Sankhani kalembedwe komwe kakugwirizana nanu.","Titha kukuthandizani kupeza saizi yoyenera.","Lumikizanani nafe pa WhatsApp mosavuta.","Tikuyankhani mwachangu momwe tingathere.","Onani zatsopano zomwe zalowa lero.","Zovala zathu zasankhidwa mosamala.","Mutha kutitumizira uthenga nthawi iliyonse.","Tikukuthokozani chifukwa chotichezera.","Khalani ndi tsiku labwino komanso lokongola.","Tiyeni tikuthandizeni kupeza zomwe mukufuna.","Mtundu uliwonse ukusonyeza umunthu wanu.","Timayamikira kukoma kwanu.","Tikufunirani zabwino pamene mukusankha."];
  try{ const s=await api('/settings'); if(s.hero_phrases){ const custom=String(s.hero_phrases).split(/\r?\n/).map(x=>x.trim()).filter(Boolean); if(custom.length) lines=custom; } }catch{}
  let i=0;
  const set=(n,animate=true)=>{ el.classList.remove('chichewa-in'); if(animate && !reduce){ el.classList.add('chichewa-out'); setTimeout(()=>{ el.textContent=lines[n]; el.classList.remove('chichewa-out'); el.classList.add('chichewa-in'); },220); } else { el.textContent=lines[n]; } };
  set(0,false);
  if(reduce || lines.length<2) return;
  if(window._chichewaTimer) clearInterval(window._chichewaTimer);
  window._chichewaTimer=setInterval(()=>{ i=(i+1)%lines.length; set(i,true); },6500);
}

let homeProductsCache=null;
function initHomeTabs(){
  const tabs=[...document.querySelectorAll('[data-home-tab]')];
  const panels=[...document.querySelectorAll('[data-home-panel]')];
  if(!tabs.length || !panels.length) return;
  const showTab=(name,push=true)=>{
    panels.forEach(p=>{p.style.display = (p.dataset.homePanel===name)?'':'none'});
    tabs.forEach(a=>a.classList.toggle('active', a.dataset.homeTab===name));
    document.getElementById('nav')?.classList.remove('show');
    if(name==='shop' || name==='new') ensureHomeProducts(name);
    if(name==='home') initHeroSlider();
    if(push){ const hash=name==='home'?'#home':`#${name}`; history.replaceState(null,'',hash); }
    window.scrollTo({top:0,behavior:'smooth'});
  };
  tabs.forEach(a=>{
    a.addEventListener('click',e=>{
      const tab=a.dataset.homeTab;
      if(!tab) return;
      // Shop/new/contact/about are handled as in-page tabs on home
      if(['home','shop','new','about','contact'].includes(tab)){
        e.preventDefault();
        showTab(tab);
      }
    });
  });
  const initial=(location.hash||'#home').replace('#','');
  const valid=['home','shop','new','about','contact'];
  showTab(valid.includes(initial)?initial:'home',false);
}
async function ensureHomeProducts(tab){
  if(!homeProductsCache){
    try{ homeProductsCache=await api('/products'); }catch(e){ homeProductsCache=[]; }
    currentProducts=homeProductsCache;
    const cats=[...new Set(homeProductsCache.map(p=>p.category).filter(Boolean))];
    const sel=document.getElementById('home-category');
    if(sel) sel.innerHTML='<option value="">All categories</option>'+cats.map(c=>`<option>${esc(c)}</option>`).join('');
  } else { currentProducts=homeProductsCache; }
  if(tab==='shop') renderHomeShop();
  if(tab==='new') renderHomeNew();
}
function renderHomeShop(){
  const grid=document.getElementById('home-shop-grid'); if(!grid) return;
  let ps=[...(homeProductsCache||[])];
  const q=(document.getElementById('home-search')?.value||'').toLowerCase();
  const cat=document.getElementById('home-category')?.value||'';
  const sort=document.getElementById('home-sort')?.value||'recent';
  ps=ps.filter(p=>{const hay=(p.name+' '+p.description+' '+p.category+' '+(p.sku||'')).toLowerCase(); return hay.includes(q)&&(!cat||p.category===cat)});
  if(sort==='price-low')ps.sort((a,b)=>(a.sale_price??a.price)-(b.sale_price??b.price));
  if(sort==='price-high')ps.sort((a,b)=>(b.sale_price??b.price)-(a.sale_price??a.price));
  grid.innerHTML=ps.map(card).join('')||emptyProducts();
}
function renderHomeNew(){
  const grid=document.getElementById('home-new-grid'); if(!grid) return;
  let ps=[...(homeProductsCache||[])];
  ps.sort((a,b)=>Number(b.id)-Number(a.id));
  grid.innerHTML=ps.slice(0,8).map(card).join('')||emptyProducts();
}

function card(p){const st=p.stock<=0?'OUT_OF_STOCK':(p.low_stock_variants>0?'LOW_STOCK':'IN_STOCK');return `<article class="product-card"><a href="/product?id=${p.id}" class="product-photo">${img(p)}${p.stock<=0?'<span class="sold">Sold out</span>':''}</a><div class="product-info"><p class="eyebrow" style="margin-bottom:4px">${esc(p.category||'')}</p><h3>${esc(p.name)}</h3><div>${money(p.sale_price??p.price)}${p.sale_price?`<span class="old-price">${money(p.price)}</span>`:""}</div><div class="muted small">${p.stock>0?`${p.stock} available`:'Currently unavailable'}</div><div class="product-actions"><a class="btn" href="/product?id=${p.id}" style="border:1px solid var(--line)">Details</a><button class="btn primary" ${p.stock<=0?"disabled":""} onclick="addCart(${p.id})">Add to bag</button></div></div></article>`}
async function loadFeatured(){try{let ps=await api("/products?featured=true");if(!ps.length)ps=await api("/products");document.getElementById("featured").innerHTML=ps.slice(0,4).map(card).join("")||emptyProducts()}catch(e){document.getElementById("featured").innerHTML=emptyProducts()}}
async function loadShop(){try{currentProducts=await api("/products");let cats=await api("/categories");let sel=document.getElementById("category");if(sel)sel.innerHTML='<option value="">All categories</option>'+cats.map(c=>`<option>${esc(c)}</option>`).join("");renderShop()}catch(e){document.getElementById("shop-grid").innerHTML=emptyProducts()}}
function renderShop(){let q=(document.getElementById("search")?.value||"").toLowerCase(),cat=document.getElementById("category")?.value||"",sort=document.getElementById("sort")?.value||"recent";let ps=currentProducts.filter(p=>{let hay=(p.name+" "+p.description+" "+p.category+" "+(p.sku||"")+" "+(p.variants||[]).map(v=>v.variant_sku+" "+v.size+" "+v.color).join(" ")).toLowerCase();return hay.includes(q)&&(!cat||p.category===cat)});if(sort==="price-low")ps.sort((a,b)=>(a.sale_price??a.price)-(b.sale_price??b.price));if(sort==="price-high")ps.sort((a,b)=>(b.sale_price??b.price)-(a.sale_price??a.price));document.getElementById("shop-grid").innerHTML=ps.map(card).join("")||emptyProducts()}
function emptyProducts(){return '<div class="muted">New pieces are on the way. Please check back soon.</div>'}
function addCart(id){let p=currentProducts.find(x=>x.id===id);if(!p){fetch(API+"/products").then(r=>r.json()).then(ps=>{currentProducts=ps;let found=ps.find(x=>x.id===id);if(found)cartAdd(found)});return}cartAdd(p)}
function addCartVariant(p,v){
  if(!p) return;
  const hasVariant=!!v;
  const stock=Number(hasVariant?v.stock_quantity:p.stock||0);
  if(stock<=0){toast('This option is out of stock');return}
  const key=hasVariant?`${p.id}:${v.id}`:`${p.id}`;
  const name=hasVariant?`${p.name} (${v.size}/${v.color})`:p.name;
  const price=Number(hasVariant?(v.selling_price??p.sale_price??p.price):(p.sale_price??p.price));
  let row=cart.find(x=>x.key===key);
  if(row) row.qty=Math.min(row.qty+1,stock);
  else cart.push({key,id:p.id,variant_id:v?.id||null,name,price,qty:1,stock});
  saveCart(); toast("Added to your bag");
}
function cartAdd(p){
  const variants=(p.variants||[]).filter(v=>Number(v.stock_quantity)>0 && v.is_active!==false);
  if(variants.length===1) return addCartVariant(p,variants[0]);
  if(variants.length>1){ location.href=`/product?id=${p.id}`; return; }
  if(Number(p.stock||0)<=0){toast('Out of stock'); return;}
  addCartVariant(p,null);
}
function saveCart(){localStorage.setItem("tc_cart",JSON.stringify(cart));updateCartCount()}
function updateCartCount(){document.querySelectorAll("#cart-count").forEach(x=>x.textContent=cart.reduce((s,p)=>s+p.qty,0))}
function openCart(){let modal=document.getElementById("cart-modal");if(!modal)return;modal.classList.add("open");let el=document.getElementById("cart-items");el.innerHTML=cart.map(p=>`<div class="cart-line"><div><strong>${esc(p.name)}</strong><br><span class="muted">${money(p.price)} · qty ${p.qty}</span></div><div><button onclick="cartQty('${esc(p.key||p.id)}',-1)">−</button> <button onclick="cartQty('${esc(p.key||p.id)}',1)">+</button> <button onclick="removeCart('${esc(p.key||p.id)}')">×</button></div></div>`).join("")||"Your bag is empty";document.getElementById("cart-total").innerHTML=`<p><strong>Total: ${money(cart.reduce((s,p)=>s+p.price*p.qty,0))}</strong></p>`}
function closeCart(){document.getElementById("cart-modal")?.classList.remove("open")}
function cartQty(key,d){key=String(key);let p=cart.find(x=>String(x.key||x.id)===key);if(p){p.qty=Math.max(1,Math.min(p.stock||99,p.qty+d));saveCart();openCart()}}
function removeCart(key){key=String(key);cart=cart.filter(p=>String(p.key||p.id)!==key);saveCart();openCart()}

function checkout(){
  if(!cart.length){toast("Your bag is empty");return}
  const total=cart.reduce((s,p)=>s+p.price*p.qty,0);
  const summary=cart.map(p=>`<div>${esc(p.name)} × ${p.qty} — <strong>${money(p.price*p.qty)}</strong></div>`).join('');
  const modal=document.getElementById('cart-modal');
  const box=modal?.querySelector('.modal-card');
  if(!box){toast('Checkout unavailable');return}
  box.innerHTML=`<button class="close" onclick="openCart()" aria-label="Back to bag">×</button><h2>Checkout</h2>
  <div class="order-summary">${summary}<hr style="border:none;border-top:1px solid var(--line);margin:10px 0"><strong>Total: ${money(total)}</strong></div>
  <form id="checkout-form" class="checkout-form">
    <label>Full name<input name="name" required autocomplete="name"></label>
    <label>WhatsApp / phone<input name="contact" required autocomplete="tel" placeholder="+265..."></label>
    <label>Delivery or pickup location<input name="location" required placeholder="Nkhotakota Boma District / area"></label>
    <label>Note (optional)<textarea name="note" rows="2" placeholder="Size, color, delivery time"></textarea></label>
    <label><input type="checkbox" name="confirm" required> I confirm my order details are correct.</label>
    <button class="btn primary wide" type="submit">Send order request on WhatsApp</button>
    <button class="btn wide" type="button" onclick="openCart()">Back to bag</button>
  </form>`;
  document.getElementById('checkout-form').onsubmit=submitCheckout;
}
async function submitCheckout(e){
  e.preventDefault();
  const f=e.target; const d=Object.fromEntries(new FormData(f));
  const total=cart.reduce((s,p)=>s+p.price*p.qty,0);
  const items=cart.map(p=>`- ${p.name} x${p.qty} (${money(p.price*p.qty)})`).join('\n');
  const msg=`Ma order ena nd liti?\n\nName: ${d.name}\nContact: ${d.contact}\nLocation: ${d.location}\nNote: ${d.note||'-'}\nOrder:\n${items}\nTotal: ${money(total)}`;
  const waUrl="https://chat.whatsapp.com/KKDXAzRiifw4FSNPM8qskX?s=sw&p=a&mlu=4&ilr=4&iam=2";
  const opened=window.open(waUrl,"_blank","noopener");
  try{ await navigator.clipboard.writeText(msg); toast("Order copied. Paste it in WhatsApp."); }
  catch{ prompt("Copy this order message and send it on WhatsApp:", msg); }
  try{
    await api("/orders",{method:"POST",body:JSON.stringify({customer:d.name,contact:d.contact,location:d.location,note:d.note||'',items:cart,total,source:'web'})});
  }catch(err){ console.warn('Order save failed',err); toast('Order message ready, but saving to system failed.'); }
  if(!opened){ window.location.assign(waUrl); }
  cart=[]; saveCart(); closeCart();
}

async function loadDetail(){let id=new URLSearchParams(location.search).get("id");try{let p=await api(`/products/${id}`);currentProducts=[p];let el=document.getElementById("product-detail");let variants=p.variants||[];let available=variants.filter(v=>Number(v.stock_quantity)>0 && v.is_active!==false);
const sizeOrder=["XXS","XS","S","M","L","XL","XXL","2XL","3XL"];
const sizeSort=(a,b)=>{const ia=sizeOrder.indexOf(String(a).toUpperCase());const ib=sizeOrder.indexOf(String(b).toUpperCase());return (ia===-1?999:ia)-(ib===-1?999:ib)||String(a).localeCompare(String(b));};
let sizes=[...new Set(available.map(v=>v.size).filter(Boolean))].sort(sizeSort);
let colors=[...new Set(available.map(v=>v.color).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
const fallbackImgs=["https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=900&q=80","https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=900&q=80","https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=80","https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=900&q=80"];
const imgs=(p.images&&p.images.length)?p.images.map(i=>i.path):fallbackImgs;
let selSize=sizes[0]||''; let selColor=colors[0]||'';
const findV=()=>available.find(v=>(!selSize||v.size===selSize)&&(!selColor||v.color===selColor))||available[0]||null;
const render=()=>{
  const sel=findV();
  const max=sel?Number(sel.stock_quantity||0):Number(p.stock||0);
  el.innerHTML=`<div class="product-detail"><div class="photos detail-gallery">${imgs.map((src,i)=>`<img src="${src}" alt="${esc(p.name)} sample ${i+1}" loading="${i?'lazy':'eager'}">`).join("")}</div><div><p class="eyebrow">${esc(p.category||'')}</p><h1 style="font-family:'Playfair Display';font-size:38px">${esc(p.name)}</h1><p class="price">${money((sel?.selling_price??p.sale_price??p.price)||0)}</p><p>${esc(p.description||'')}</p>
  <div class="variant-picker"><div><strong>Available sizes</strong><div class="pick-row">${sizes.map(s=>`<button class="pick ${s===selSize?'active':''}" data-size="${esc(s)}">${esc(s)}</button>`).join('')||'<span class="muted">Ask us</span>'}</div></div>
  <div style="margin-top:10px"><strong>Available colours</strong><div class="pick-row">${colors.map(c=>`<button class="pick ${c===selColor?'active':''}" data-color="${esc(c)}">${esc(c)}</button>`).join('')||'<span class="muted">Ask us</span>'}</div></div></div>
  <p id="variant-stock" class="muted">${sel?`${sel.stock_quantity} available for ${esc(sel.size)} / ${esc(sel.color)}`:(p.stock>0?`${p.stock} available`:'Currently unavailable')}</p>
  <div class="product-actions" style="margin-top:14px"><button class="btn primary" id="detail-add" ${(sel?sel.stock_quantity<=0:p.stock<=0)?"disabled":""}>Add to bag</button><button class="btn" id="detail-enquire">Ask about this item</button></div>
  ${available.length?`<div class="table-wrap" style="margin-top:16px"><table class="admin-table compact"><thead><tr><th>Size</th><th>Colour</th><th>Stock</th><th>Status</th></tr></thead><tbody>${available.map(v=>`<tr><td>${esc(v.size)}</td><td>${esc(v.color)}</td><td>${v.stock_quantity}</td><td>${statusBadge(stockStatus(v))}</td></tr>`).join('')}</tbody></table></div>`:''}
  </div></div>`;
  el.querySelectorAll('[data-size]').forEach(b=>b.onclick=()=>{selSize=b.dataset.size; render();});
  el.querySelectorAll('[data-color]').forEach(b=>b.onclick=()=>{selColor=b.dataset.color; render();});
  el.querySelector('#detail-add').onclick=()=>{const v=findV(); addCartVariant(p,v);};
  el.querySelector('#detail-enquire').onclick=()=>enquireProduct(p.id);
};
render();
}catch(e){document.getElementById("product-detail").innerHTML=`<p class="muted">Product not found.</p>`}}
async function enquireProduct(id){let name=prompt("Your name");if(!name)return;let contact=prompt("WhatsApp/phone (optional)")||"";let message=prompt("Your question");if(!message)return;try{await api("/enquiries",{method:"POST",body:JSON.stringify({name,contact,product_id:id,message})});toast("Enquiry sent!")}catch(e){toast(e.message)}}
function loginSetup(){
  const form=document.getElementById("login-form"); if(!form) return;
  const saved=JSON.parse(localStorage.getItem("tc_login_remember")||"null");
  const username=form.elements.username;
  const password=form.elements.password;
  const remember=form.elements.remember;
  if(saved){
    if(saved.username) username.value=saved.username;
    /* password not remembered for security */
    if(remember) remember.checked=true;
  } else {
    // first-time prefill for demo
    if(!username.value) username.value="tahira";
    if(!password.value) password.value="Tahira@123"; // demo only; not stored
  }
  form.onsubmit=async e=>{
    e.preventDefault();
    let d=Object.fromEntries(new FormData(form));
    try{
      let r=await api("/login",{method:"POST",body:JSON.stringify({username:d.username,password:d.password})});
      token=r.token; localStorage.setItem("tc_token",token);
      if(form.elements.remember?.checked){
        localStorage.setItem("tc_login_remember",JSON.stringify({username:d.username}));
      } else {
        localStorage.removeItem("tc_login_remember");
      }
      location.href="/admin";
    }catch(err){document.getElementById("login-error").textContent=err.message}
  }
}

/* Admin */
function showSection(id){document.querySelectorAll('.admin-section').forEach(s=>s.classList.remove('active'));document.getElementById(id)?.classList.add('active');document.querySelectorAll('.nav-link[data-section]').forEach(a=>a.classList.toggle('active',a.dataset.section===id));const titles={dashboard:'Inventory Dashboard',products:'Products',inventory:'Inventory',restock:'Restock Inventory',history:'Stock History',lowstock:'Low Stock',orders:'Order Requests',enquiries:'Customer Enquiries',phrases:'Chichewa Market Phrases',settings:'Settings'};const h=document.getElementById('admin-title');if(h)h.textContent=titles[id]||'Closset Management';if(window.innerWidth<900)document.getElementById('sidebar')?.classList.remove('show');refreshSection(id)}
async function initAdmin(){if(!token){location.href="/login";return}try{await refreshSection('dashboard');await loadSettingsIntoForm();await loadPhrasesIntoForm();}catch(e){console.error(e);if(String(e).includes('401')||String(e).includes('sign-in')){localStorage.removeItem("tc_token");token=null;location.href="/login"}}}
async function refreshCurrentSection(){const active=document.querySelector('.admin-section.active')?.id||'dashboard';await refreshSection(active);toast('Refreshed')}
async function refreshSection(id){
  if(id==='dashboard')return loadDashboard();
  if(id==='products')return adminProducts();
  if(id==='inventory')return loadInventory();
  if(id==='restock')return loadRestockForm();
  if(id==='history')return loadHistory();
  if(id==='lowstock')return loadLowStock();
  if(id==='orders')return adminOrders();
  if(id==='enquiries')return adminEnquiries();
  if(id==='phrases')return loadPhrasesIntoForm();
  if(id==='settings')return loadSettingsIntoForm();
}
async function loadDashboard(){const c=await api('/inventory/dashboard');document.getElementById('metrics').innerHTML=[
  ['Total products',c.total_products],['Active variants',c.total_active_variants],['Units in stock',c.units_in_stock],['Low stock variants',c.low_stock_variants],['Out of stock',c.out_of_stock_variants],['Inventory cost value',money(c.inventory_cost_valuation)],['Inventory selling value',money(c.inventory_selling_valuation)],['Recent movements',c.recent_stock_movements?.length||0]
].map(x=>`<div class="metric"><span>${esc(x[0])}</span><strong>${esc(x[1])}</strong></div>`).join('');
 const low=await api('/inventory/low-stock?limit=8'); const out=await api('/inventory/out-of-stock?limit=8');
 document.getElementById('dash-low-stock').innerHTML=variantTable(low.items||[],false);
 document.getElementById('dash-out-stock').innerHTML=variantTable(out.items||[],false);
 document.getElementById('dash-movements').innerHTML=movementTable(c.recent_stock_movements||[]);
 document.getElementById('dash-restocked').innerHTML=`<table class="admin-table"><thead><tr><th>Date</th><th>Product</th><th>Variant</th><th>Qty</th><th>Supplier</th><th>Ref</th></tr></thead><tbody>${(c.recently_restocked_products||[]).map(r=>`<tr><td>${esc(r.created_at||'')}</td><td>${esc(r.product_name||'')}</td><td>${esc(r.variant_sku||'')} ${esc([r.size,r.color].filter(Boolean).join('/'))}</td><td>${esc(r.quantity_change)}</td><td>${esc(r.supplier||'')}</td><td>${esc(r.reference_number||'')}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No restocks yet</td></tr>'}</tbody></table>`;
}
function movementTable(rows){return `<table class="admin-table"><thead><tr><th>Date</th><th>Product</th><th>Variant</th><th>Movement</th><th>Change</th><th>Before</th><th>After</th><th>By</th><th>Ref</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.created_at||'')}</td><td>${esc(r.product_name||'')}</td><td>${esc(r.variant_sku||'')}</td><td>${esc((r.movement_type||'').replaceAll('_',' '))}</td><td>${esc(r.quantity_change)}</td><td>${esc(r.quantity_before)}</td><td>${esc(r.quantity_after)}</td><td>${esc(r.administrator||'')}</td><td>${esc(r.reference_number||'')}</td></tr>`).join('')||'<tr><td colspan="9" class="muted">No movements yet</td></tr>'}</tbody></table>`}
function variantTable(rows, selectable=true){return `<table class="admin-table"><thead><tr>${selectable?'<th></th>':''}<th>Product</th><th>Variant SKU</th><th>Size</th><th>Colour</th><th>Stock</th><th>Status</th><th>Threshold</th><th>Actions</th></tr></thead><tbody>${rows.map(v=>`<tr><${selectable?`td><input type="checkbox" ${selectedVariants.has(v.id)?'checked':''} onchange="toggleVariantSel(${v.id},this.checked)"></td>`:''}<td>${esc(v.product_name||'')}</td><td>${esc(v.variant_sku||'')}</td><td>${esc(v.size||'')}</td><td>${esc(v.color||'')}</td><td>${esc(v.stock_quantity)}</td><td>${statusBadge(v.status||stockStatus(v))}</td><td>${esc(v.low_stock_threshold)}</td><td><button class="btn tiny" onclick='openVariantModal(${JSON.stringify(v).replace(/'/g,"&#39;")})'>Edit</button> <button class="btn tiny" onclick="quickRestock(${v.product_id},${v.id})">Restock</button></td></tr>`).join('')||`<tr><td colspan="${selectable?9:8}" class="muted">No items</td></tr>`}</tbody></table>`}
function toggleVariantSel(id,checked){if(checked)selectedVariants.add(id); else selectedVariants.delete(id); const el=document.getElementById('bulk-selected'); if(el)el.textContent=`${selectedVariants.size} selected`;}

async function adminProducts(){let ps=await api('/admin/products');let q=(document.getElementById('product-search')?.value||'').toLowerCase();let status=document.getElementById('product-filter-status')?.value||'';ps=ps.filter(p=>{let hay=(p.name+' '+p.sku+' '+p.category+' '+(p.brand||'')).toLowerCase();let ok=!q||hay.includes(q);let ok2=!status||(status==='active'?p.active:!p.active);return ok&&ok2});let el=document.getElementById('product-admin');el.innerHTML=`<table class="admin-table"><thead><tr><th>Photo</th><th>Product</th><th>SKU</th><th>Category</th><th>Price</th><th>Stock</th><th>Variants</th><th>Status</th><th>Actions</th></tr></thead><tbody>${ps.map(p=>`<tr><td>${p.images?.[0]?`<img src="${p.images[0].path}" alt="">`:'—'}</td><td><strong>${esc(p.name)}</strong><br><small class="muted">${esc(p.brand||'')}</small></td><td>${esc(p.sku||'')}</td><td>${esc(p.category||'')}</td><td>${money(p.sale_price??p.price)}</td><td>${esc(p.stock)}</td><td>${esc((p.variants||[]).length)}</td><td>${p.active?statusBadge((p.variants||[]).some(v=>v.stock_quantity<=0)?'OUT_OF_STOCK':((p.variants||[]).some(v=>v.stock_quantity>0&&v.stock_quantity<= (v.low_stock_threshold??3))?'LOW_STOCK':'IN_STOCK')):'<span class="badge">Inactive</span>'}</td><td class="actions"><button class="btn tiny" onclick='editProduct(${JSON.stringify(p).replace(/'/g,"&#39;")})'>Edit</button> <button class="btn tiny" onclick="openInventoryMatrix(${p.id})">Matrix</button> <button class="btn tiny danger" onclick="deleteProduct(${p.id})">Delete</button></td></tr>`).join('')||'<tr><td colspan="9" class="muted">No products</td></tr>'}</tbody></table>`}
function showProductForm(p=null){let f=document.getElementById('product-form');f.reset();f.elements.id.value=p?.id||'';document.getElementById('product-form-title').textContent=p?'Edit product':'Add product';if(p){['name','description','category','brand','price','sale_price','cost_price','sku','stock','sizes','colors','supplier','low_stock_threshold','date_added'].forEach(k=>{if(f.elements[k])f.elements[k].value=p[k]??(k==='low_stock_threshold'?3:'')});f.elements.featured.checked=!!p.featured;f.elements.active.checked=!!p.active;document.getElementById('image-preview').innerHTML=(p.images||[]).map(i=>`<div class="preview-item"><img src="${i.path}"><button type="button" class="btn tiny danger" onclick="deleteImage(${i.id})">Remove</button></div>`).join('')}else{f.elements.low_stock_threshold.value=3;f.elements.active.checked=true;document.getElementById('image-preview').innerHTML=''}uploadFiles=[];document.getElementById('product-modal').classList.add('open')}
function closeProductForm(){document.getElementById('product-modal').classList.remove('open')}
function editProduct(p){showProductForm(p)}
function previewFiles(e){uploadFiles=[...e.target.files];document.getElementById('image-preview').innerHTML=uploadFiles.map(f=>`<img src="${URL.createObjectURL(f)}" alt="preview">`).join('')}
async function saveProduct(e){e.preventDefault();let f=e.target,d=Object.fromEntries(new FormData(f));['price','sale_price','cost_price','stock','low_stock_threshold'].forEach(k=>{if(d[k]===''||d[k]===undefined)d[k]=null; else d[k]=Number(d[k])});d.featured=f.elements.featured.checked;d.active=f.elements.active.checked;d.stock=Number(d.stock||0);d.low_stock_threshold=Number(d.low_stock_threshold||3);try{let pid;if(d.id){pid=Number(d.id);await api(`/admin/products/${pid}`,{method:'PUT',body:JSON.stringify(d)})}else{let r=await api('/admin/products',{method:'POST',body:JSON.stringify(d)});pid=r.id}for(let file of uploadFiles){let fd=new FormData();fd.append('file',file);await api(`/admin/products/${pid}/images`,{method:'POST',body:fd})}toast('Product saved');closeProductForm();await refreshCurrentSection();}catch(err){toast(err.message)}}
async function deleteProduct(id){if(!confirm('Delete this product and its inventory records?'))return;try{await api(`/admin/products/${id}`,{method:'DELETE'});toast('Product deleted');await refreshCurrentSection()}catch(e){toast(e.message)}}
async function deleteImage(id){if(!confirm('Remove this image?'))return;try{await api(`/admin/images/${id}`,{method:'DELETE'});toast('Image removed');await refreshCurrentSection();closeProductForm()}catch(e){toast(e.message)}}

/* Inventory */
async function loadInventory(){await loadCategoryOptions();const params=new URLSearchParams();['q','category','status','active'].forEach(k=>{const v=document.getElementById('inv-'+k)?.value; if(v)params.set(k,v)});params.set('limit','200');const data=await api('/inventory?'+params.toString());adminInventory=data.items||[];renderInventory(adminInventory)}
function renderInventory(items){const el=document.getElementById('inventory-admin');el.innerHTML=`<table class="admin-table"><thead><tr><th></th><th>Product</th><th>Category</th><th>Total stock</th><th>Variants</th><th>Low/out</th><th>Matrix</th></tr></thead><tbody>${items.map(p=>`<tr><td></td><td><strong>${esc(p.name)}</strong><br><small class="muted">${esc(p.sku||'')}</small></td><td>${esc(p.category||'')}</td><td>${esc(p.total_stock)}</td><td>${esc(p.variant_count)}</td><td>${statusBadge(p.out_of_stock_variants>0?'OUT_OF_STOCK':(p.low_stock_variants>0?'LOW_STOCK':'IN_STOCK'))} <span class="muted small">${p.low_stock_variants||0} low / ${p.out_of_stock_variants||0} out</span></td><td><button class="btn tiny" onclick="openInventoryMatrix(${p.id})">Open matrix</button></td></tr><tr class="matrix-row"><td colspan="7">${renderMatrixTable(p)}</td></tr>`).join('')||'<tr><td colspan="7" class="muted">No inventory found</td></tr>'}</tbody></table>`;document.getElementById('bulk-selected').textContent=`${selectedVariants.size} selected`;}
function renderMatrixTable(p){const variants=p.variants||[];if(!variants.length)return '<div class="muted small">No variants</div>';const sizes=[...new Set(variants.map(v=>v.size))];const colors=[...new Set(variants.map(v=>v.color))];const map={};variants.forEach(v=>{map[v.size+'||'+v.color]=v});return `<div class="matrix-wrap"><table class="admin-table matrix"><thead><tr><th>Size / Colour</th>${colors.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${sizes.map(s=>`<tr><th>${esc(s)}</th>${colors.map(c=>{const v=map[s+'||'+c]; if(!v) return '<td class="muted">—</td>'; const cls=stockStatus(v)==='OUT_OF_STOCK'?'cell-bad':(stockStatus(v)==='LOW_STOCK'?'cell-warn':'cell-ok'); return `<td class="${cls}"><button class="cell-btn" onclick='openVariantModal(${JSON.stringify(v).replace(/'/g,"&#39;")})'><strong>${v.stock_quantity}</strong><small>${esc(v.variant_sku)}</small></button></td>`}).join('')}</tr>`).join('')}</tbody></table></div>`}
async function openInventoryMatrix(productId){showSection('inventory');await loadInventory();const row=[...document.querySelectorAll('#inventory-admin strong')].find(n=>{const tr=n.closest('tr');return tr && tr.innerHTML.includes(`openInventoryMatrix(${productId})`)});row?.scrollIntoView({behavior:'smooth',block:'center'})}
async function loadCategoryOptions(){try{const cats=await api('/categories');const sel=document.getElementById('inv-category');if(!sel) return;const cur=sel.value;sel.innerHTML='<option value="">All categories</option>'+cats.map(c=>`<option ${c===cur?'selected':''}>${esc(c)}</option>`).join('')}catch{}}

function openVariantModal(v){const f=document.getElementById('variant-form');f.reset();f.elements.variant_id.value=v.id;f.elements.product_id.value=v.product_id;f.elements.product_name.value=v.product_name||'';f.elements.variant_sku.value=v.variant_sku||'';f.elements.size.value=v.size||'';f.elements.color.value=v.color||'';f.elements.stock_quantity.value=v.stock_quantity??0;f.elements.low_stock_threshold.value=v.low_stock_threshold??3;f.elements.cost_price.value=v.cost_price??'';f.elements.selling_price.value=v.selling_price??'';f.elements.barcode.value=v.barcode??'';f.elements.is_active.checked=!!v.is_active;f.elements.reason.value='';f.elements.reference_number.value='';document.getElementById('variant-modal').classList.add('open')}
function closeVariantModal(){document.getElementById('variant-modal').classList.remove('open')}
async function saveVariant(e){e.preventDefault();const f=e.target;const id=f.elements.variant_id.value;const payload={variant_sku:f.elements.variant_sku.value,size:f.elements.size.value,color:f.elements.color.value,stock_quantity:Number(f.elements.stock_quantity.value),low_stock_threshold:Number(f.elements.low_stock_threshold.value),cost_price:f.elements.cost_price.value===''?null:Number(f.elements.cost_price.value),selling_price:f.elements.selling_price.value===''?null:Number(f.elements.selling_price.value),barcode:f.elements.barcode.value||null,is_active:f.elements.is_active.checked,reason:f.elements.reason.value||'Variant updated',reference_number:f.elements.reference_number.value||''};try{await api(`/inventory/variants/${id}`,{method:'PUT',body:JSON.stringify(payload)});toast('Variant saved');closeVariantModal();await refreshCurrentSection()}catch(err){toast(err.message)}}
async function quickRestock(productId,variantId){showSection('restock');await loadRestockForm();document.getElementById('restock-product').value=String(productId);await loadRestockVariants();document.getElementById('restock-variant').value=String(variantId)}
async function applyBulkVariants(){if(!selectedVariants.size){toast('Select at least one variant');return}const threshold=document.getElementById('bulk-threshold').value;const active=document.getElementById('bulk-active').value;const stock=document.getElementById('bulk-stock').value;const payload={variant_ids:[...selectedVariants],reason:'Bulk inventory update'};if(threshold!=='')payload.low_stock_threshold=Number(threshold);if(active!=='')payload.is_active=active==='true';if(stock!=='')payload.stock_quantity=Number(stock);try{await api('/inventory/bulk/variants',{method:'POST',body:JSON.stringify(payload)});toast('Bulk update applied');selectedVariants.clear();await loadInventory()}catch(e){toast(e.message)}}

/* Restock */
async function loadRestockForm(){const ps=await api('/admin/products');const sel=document.getElementById('restock-product');const cur=sel.value;sel.innerHTML='<option value="">Select product</option>'+ps.map(p=>`<option value="${p.id}">${esc(p.name)} (${esc(p.sku||'no SKU')})</option>`).join('');if(cur)sel.value=cur;await loadRestockVariants()}
async function loadRestockVariants(){const pid=document.getElementById('restock-product').value;const sel=document.getElementById('restock-variant');if(!pid){sel.innerHTML='<option value="">Select variant</option>';return}const data=await api(`/inventory/matrix/${pid}`);sel.innerHTML='<option value="">Select variant</option>'+data.variants.map(v=>`<option value="${v.id}">${esc(v.size)} / ${esc(v.color)} — ${esc(v.variant_sku)} (stock ${v.stock_quantity})</option>`).join('')}
async function submitRestock(e){e.preventDefault();const d=Object.fromEntries(new FormData(e.target));const payload={product_id:Number(d.product_id),variant_id:Number(d.variant_id),quantity_received:Number(d.quantity_received),supplier:d.supplier||'',cost_price:d.cost_price===''?null:Number(d.cost_price),reference_number:d.reference_number||'',notes:d.notes||''};try{await api('/inventory/restock',{method:'POST',body:JSON.stringify(payload)});toast('Restock recorded');e.target.reset();await loadRestockForm();await loadDashboard();}catch(err){toast(err.message)}}

/* History */
async function loadHistory(){const params=new URLSearchParams();const q=document.getElementById('hist-q')?.value;const type=document.getElementById('hist-type')?.value;const from=document.getElementById('hist-from')?.value;const to=document.getElementById('hist-to')?.value;if(q)params.set('sku',q);if(type)params.set('movement_type',type);if(from)params.set('date_from',from);if(to)params.set('date_to',to);params.set('limit','200');const data=await api('/inventory/history?'+params.toString());document.getElementById('history-admin').innerHTML=movementTable(data.items||[])}
async function exportHistoryCSV(){const params=new URLSearchParams();const q=document.getElementById('hist-q')?.value;const type=document.getElementById('hist-type')?.value;const from=document.getElementById('hist-from')?.value;const to=document.getElementById('hist-to')?.value;if(q)params.set('sku',q);if(type)params.set('movement_type',type);if(from)params.set('date_from',from);if(to)params.set('date_to',to);await downloadAuthed('/inventory/history/export?'+params.toString(),'inventory-history.csv')}
async function exportInventoryCSV(){await downloadAuthed('/inventory/export','inventory-export.csv')}
async function downloadAuthed(path,filename){const r=await fetch(API+path,{headers:{'Authorization':'Bearer '+token}});if(!r.ok){toast('Export failed');return}const blob=await r.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url)}

/* Low stock */
async function loadLowStock(){const q=document.getElementById('low-q')?.value||'';const sort=document.getElementById('low-sort')?.value||'urgency';const [low,out]=await Promise.all([api('/inventory/low-stock?limit=200&q='+encodeURIComponent(q)),api('/inventory/out-of-stock?limit=200&q='+encodeURIComponent(q))]);let lowItems=low.items||[], outItems=out.items||[];const sorter=(a,b)=>{if(sort==='quantity')return a.stock_quantity-b.stock_quantity; if(sort==='name')return String(a.product_name).localeCompare(String(b.product_name)); return (a.stock_quantity-a.low_stock_threshold)-(b.stock_quantity-b.low_stock_threshold)};lowItems.sort(sorter);outItems.sort((a,b)=>sort==='name'?String(a.product_name).localeCompare(String(b.product_name)):a.stock_quantity-b.stock_quantity);document.getElementById('out-stock-list').innerHTML=variantTable(outItems,false);document.getElementById('low-stock-list').innerHTML=variantTable(lowItems,false);}

/* Import */
async function previewInventoryImport(file){if(!file)return;const fd=new FormData();fd.append('file',file);try{const res=await api('/inventory/import?apply=false',{method:'POST',body:fd});importPreviewRows=res.preview||[];const box=document.getElementById('inventory-import-preview');box.style.display='block';box.innerHTML=`<div class="section-heading"><h3>CSV Import Preview</h3><div class="header-actions"><button class="btn" onclick="applyInventoryImport()">Apply import</button></div></div>${res.errors?.length?`<div class="error-box"><strong>Validation errors:</strong><ul>${res.errors.map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`:`<p class="muted">${res.count||0} rows validated. No changes applied yet.</p>`}<div class="table-wrap"><table class="admin-table"><thead><tr><th>Line</th><th>Product</th><th>Variant SKU</th><th>From</th><th>To</th><th>Delta</th></tr></thead><tbody>${(res.preview||[]).map(r=>`<tr><td>${r.line}</td><td>${esc(r.product_name||'')}</td><td>${esc(r.variant_sku||'')}</td><td>${r.from}</td><td>${r.to}</td><td>${r.delta}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No preview rows</td></tr>'}</tbody></table></div>`}catch(e){toast(e.message)}}
async function applyInventoryImport(){const file=document.getElementById('inventory-import-file').files[0];if(!file){toast('Choose a CSV file first');return}const fd=new FormData();fd.append('file',file);try{const res=await api('/inventory/import?apply=true',{method:'POST',body:fd});if(res.errors?.length){toast('Import validation failed');await previewInventoryImport(file);return}toast('Import applied');document.getElementById('inventory-import-preview').style.display='none';document.getElementById('inventory-import-file').value='';await loadInventory();await loadDashboard();}catch(e){toast(e.message)}}

/* Enquiries/Orders/Settings */
async function adminEnquiries(){let rows=await api('/admin/enquiries');document.getElementById('enquiry-admin').innerHTML=rows.map(r=>`<div class="panel" style="margin-bottom:12px"><strong>${esc(r.name)} · ${esc(r.product_name||'General')}</strong><p>${esc(r.message)}</p><p class="muted small">${esc(r.contact||'')} · ${esc(r.created_at||'')}</p><div class="actions"><select onchange="enquiryStatus(${r.id},this.value)">${['new','read','replied','resolved','archived'].map(s=>`<option ${s===r.status?'selected':''}>${s}</option>`).join('')}</select> <button class="btn tiny danger" onclick="deleteEnquiry(${r.id})">Delete</button> ${r.contact?`<a class="btn tiny" target="_blank" href="https://wa.me/${String(r.contact).replace(/\D/g,'')}?text=${encodeURIComponent('Hello '+r.name+', regarding your enquiry about '+(r.product_name||'our closset'))}">WhatsApp</a>`:''}</div></div>`).join('')||'<p class="muted">No enquiries yet</p>'}
async function enquiryStatus(id,s){await api(`/admin/enquiries/${id}?status=${encodeURIComponent(s)}`,{method:'PATCH'});toast('Status updated')}
async function deleteEnquiry(id){if(!confirm('Delete enquiry?'))return;await api(`/admin/enquiries/${id}`,{method:'DELETE'});adminEnquiries()}
async function adminOrders(){let rows=await api('/admin/orders');let statuses=['pending','confirmed','paid','processing','ready for collection','dispatched','delivered','cancelled'];document.getElementById('order-admin').innerHTML=rows.map(r=>`<div class="panel" style="margin-bottom:12px"><strong>Order #${r.id} · ${esc(r.customer)}</strong><p class="muted small">${esc(r.contact||'')} · ${money(r.total)} · ${esc(r.created_at||'')}</p><div class="muted small">${(()=>{try{return JSON.parse(r.items||'[]').map(i=>`${esc(i.name)} × ${i.qty}`).join(', ')}catch{return ''}})()}</div><select onchange="orderStatus(${r.id},this.value)">${statuses.map(s=>`<option ${s===r.status?'selected':''}>${s}</option>`).join('')}</select></div>`).join('')||'<p class="muted">No orders yet</p>'}
async function orderStatus(id,s){await api(`/admin/orders/${id}?status=${encodeURIComponent(s)}`,{method:'PATCH'});toast('Order status updated')}
async function loadSettingsIntoForm(){let s=await api('/settings');let f=document.getElementById('settings-form');if(f){Object.keys(s).forEach(k=>{if(f.elements[k])f.elements[k].value=s[k]});}let pf=document.getElementById('phrases-form');if(pf?.elements.hero_phrases && s.hero_phrases!=null) pf.elements.hero_phrases.value=s.hero_phrases; window.currency=s.currency||'MK'}
async function loadPhrasesIntoForm(){let s=await api('/settings');let f=document.getElementById('phrases-form');if(f?.elements.hero_phrases && s.hero_phrases!=null) f.elements.hero_phrases.value=s.hero_phrases;}
async function savePhrases(e){e.preventDefault();let d=Object.fromEntries(new FormData(e.target));try{await api('/admin/settings',{method:'PUT',body:JSON.stringify({hero_phrases:d.hero_phrases||''})});toast('Phrases saved. Refresh storefront to see changes.')}catch(err){toast(err.message)}}
async function saveSettings(e){e.preventDefault();let d=Object.fromEntries(new FormData(e.target));try{await api('/admin/settings',{method:'PUT',body:JSON.stringify(d)});window.currency=d.currency||window.currency;toast('Settings saved')}catch(e){toast(e.message)}}
async function logout(){try{await api('/logout',{method:'POST'})}catch{}localStorage.removeItem('tc_token');token=null;location.href='/login'}
