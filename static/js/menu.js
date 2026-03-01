// TABLE_NO aur CLIENT_ID — HTML template mein inject hote hain

// ── State ──
const plate = {}; // { itemName: { qty, price } }

function parsePrice(priceStr) {
    return parseInt(priceStr.replace(/[^0-9]/g, '')) || 0;
}

// ── Add to Plate ──
function addToPlate(name, price, btn) {
    if (!plate[name]) {
        plate[name] = { qty: 1, price };
        const wrapper = btn.parentElement;
        wrapper.innerHTML = `
            <div class="qty-controls">
                <button class="qty-btn" onclick="changeQty('${name}', -1, this)">−</button>
                <span class="qty-num" id="qty-${name.replace(/\s/g,'_')}">1</span>
                <button class="qty-btn" onclick="changeQty('${name}', 1, this)">+</button>
            </div>`;
    }
    updatePlateUI();
}

function changeQty(name, delta, btn) {
    if (!plate[name]) return;
    plate[name].qty += delta;

    if (plate[name].qty <= 0) {
        delete plate[name];
        const wrapper = btn.closest('.add-btn-wrapper');
        const price = wrapper.closest('.dish-card').dataset.price;
        wrapper.innerHTML = `<button class="add-btn" onclick="addToPlate('${name}', '${price}', this)">+</button>`;
    } else {
        const id = `qty-${name.replace(/\s/g,'_')}`;
        document.getElementById(id).textContent = plate[name].qty;
    }
    updatePlateUI();
}

function updatePlateUI() {
    const items = Object.entries(plate);
    const totalQty = items.reduce((s, [, v]) => s + v.qty, 0);
    const totalPrice = items.reduce((s, [, v]) => s + parsePrice(v.price) * v.qty, 0);

    const btn = document.getElementById('plate-btn');
    document.getElementById('plate-count').textContent = totalQty;
    document.getElementById('plate-total').textContent = totalQty > 0 ? `• INR ${totalPrice}` : '';
    document.getElementById('drawer-total-price').textContent = `INR ${totalPrice}`;

    if (totalQty > 0) btn.classList.add('visible');
    else btn.classList.remove('visible');

    const drawerItems = document.getElementById('drawer-items');
    if (items.length === 0) {
        drawerItems.innerHTML = `<div class="empty-plate"><i class="fas fa-utensils"></i>Your plate is empty</div>`;
        return;
    }

    drawerItems.innerHTML = items.map(([name, { qty, price }]) => `
        <div class="drawer-item">
            <div class="qty-controls">
                <button class="qty-btn" onclick="changeQty('${name}', -1, this)">−</button>
                <span class="qty-num" id="dqty-${name.replace(/\s/g,'_')}">${qty}</span>
                <button class="qty-btn" onclick="changeQty('${name}', 1, this)">+</button>
            </div>
            <div class="drawer-item-name">${name}</div>
            <div class="drawer-item-price">INR ${parsePrice(price) * qty}</div>
        </div>
    `).join('');
}

// ── Drawer ──
let drawerOpen = false;
function toggleDrawer() {
    drawerOpen = !drawerOpen;
    document.getElementById('plate-drawer').classList.toggle('open', drawerOpen);
    document.getElementById('overlay').classList.toggle('show', drawerOpen);
}

// ── Category Tabs ──
document.getElementById('tabs').addEventListener('click', (e) => {
    const tab = e.target.closest('.tab');
    if (!tab) return;

    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    const cat = tab.dataset.cat;
    document.querySelectorAll('.category-section').forEach(section => {
        if (cat === 'all' || section.dataset.section === cat) {
            section.style.display = 'block';
        } else {
            section.style.display = 'none';
        }
    });
});

// ── Place Order ──
async function placeOrder() {
    const entries = Object.entries(plate);
    if (!entries.length) return;

    if (!TABLE_NO) {
        alert('Please scan your table QR code to place an order.');
        return;
    }

    const items = entries.map(([name, { qty, price }]) => ({
        name, qty, price: parsePrice(price)
    }));
    const total = items.reduce((s, i) => s + i.qty * i.price, 0);

    const res = await fetch(`/api/order/${CLIENT_ID}/${TABLE_NO}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items, total })
    });

    if (res.ok) {
        Object.keys(plate).forEach(k => delete plate[k]);
        document.querySelectorAll('.add-btn-wrapper').forEach(w => {
            const card = w.closest('.dish-card');
            const name  = card.dataset.name;
            const price = card.dataset.price;
            w.innerHTML = `<button class="add-btn" onclick="addToPlate('${name}','${price}',this)">+</button>`;
        });
        updatePlateUI();
        toggleDrawer();
        const msg = document.createElement('div');
        msg.style.cssText = `position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
            background:var(--secondary);color:white;padding:20px 32px;border-radius:16px;
            font-size:1rem;font-weight:600;z-index:999;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,0.3)`;
        msg.innerHTML = `✅ Order placed!<br><small style="opacity:0.7;font-weight:400">Table ${TABLE_NO}</small>`;
        document.body.appendChild(msg);
        setTimeout(() => msg.remove(), 2500);
    } else {
        const err = await res.json();
        alert('❌ ' + (err.detail || 'Something went wrong'));
    }
}
