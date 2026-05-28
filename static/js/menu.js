// TABLE_NO aur CLIENT_ID — HTML se inject hote hain

const plate  = {};   // { key: { qty, price, displayName, baseName, ddid, idx } }
const keyMap = {};   // safeKey -> originalKey

function parsePrice(p) {
    return parseInt(String(p).replace(/[^0-9]/g, '')) || 0;
}

function sk(str) {
    return str.replace(/[^a-zA-Z0-9]/g, '_');
}

function findCard(name) {
    return Array.from(document.querySelectorAll('.dish-card'))
        .find(c => c.dataset.name === name) || null;
}

function savePlateToStorage() {
    localStorage.setItem('zentable_plate_' + CLIENT_ID, JSON.stringify(plate));
    localStorage.setItem('zentable_keymap_' + CLIENT_ID, JSON.stringify(keyMap));
}

function loadPlateFromStorage() {
    try {
        const storedPlate = localStorage.getItem('zentable_plate_' + CLIENT_ID);
        const storedKeyMap = localStorage.getItem('zentable_keymap_' + CLIENT_ID);
        if (storedPlate) {
            Object.assign(plate, JSON.parse(storedPlate));
        }
        if (storedKeyMap) {
            Object.assign(keyMap, JSON.parse(storedKeyMap));
        }
        if (Object.keys(plate).length > 0) {
            Object.values(plate).forEach(item => {
                const sizeLabel = item.displayName !== item.baseName
                    ? item.displayName.replace(item.baseName + ' (', '').replace(')', '')
                    : '';
                updateCtrl(item.ddid, item.idx, item.baseName, sizeLabel, item.price, item.qty);
                updateCardBadge(item.baseName);
            });
            renderDrawer();
            updateTotals();
        }
    } catch (e) {
        console.error("Failed to load plate from local storage:", e);
    }
}

// ─────────────────────────────────────────
// EVENT LISTENER
// ─────────────────────────────────────────
document.addEventListener('click', function(e) {

    // 1. Size toggle button (+ on card) — open/close dropdown
    const sizeToggle = e.target.closest('.js-size-toggle');
    if (sizeToggle) {
        e.stopPropagation();
        const ddId = sizeToggle.dataset.ddid;
        const dd = document.getElementById(ddId);
        if (!dd) return;
        const wasOpen = dd.classList.contains('open');
        document.querySelectorAll('.size-dropdown.open').forEach(d => d.classList.remove('open'));
        if (!wasOpen) dd.classList.add('open');
        return;
    }

    // 2. + button inside dropdown row
    const sizeAdd = e.target.closest('.js-size-add');
    if (sizeAdd) {
        e.stopPropagation();
        addItem(
            sizeAdd.dataset.dish,
            sizeAdd.dataset.label,
            sizeAdd.dataset.price,
            sizeAdd.dataset.ddid,
            sizeAdd.dataset.idx
        );
        return;
    }

    // 3. − button inside dropdown row
    const sizeMinus = e.target.closest('.js-size-minus');
    if (sizeMinus) {
        e.stopPropagation();
        removeItem(
            sizeMinus.dataset.dish,
            sizeMinus.dataset.label,
            sizeMinus.dataset.ddid,
            sizeMinus.dataset.idx
        );
        return;
    }

    // 4. Drawer qty buttons
    const qtyBtn = e.target.closest('.js-qty');
    if (qtyBtn) {
        const safeK = qtyBtn.dataset.sk;
        const delta = parseInt(qtyBtn.dataset.delta);
        const realKey = keyMap[safeK];
        if (realKey !== undefined) drawerChangeQty(realKey, delta);
        return;
    }

    // 5. Locked button
    if (e.target.closest('.js-locked')) {
        showOrderingLocked();
        return;
    }

    // 6. Dish card click — dropdown toggle
    const dishCard = e.target.closest('.dish-card');
    if (dishCard) {
        const ddId = dishCard.dataset.ddid;
        const dd = document.getElementById(ddId);
        if (!dd) return;
        const wasOpen = dd.classList.contains('open');
        document.querySelectorAll('.size-dropdown.open').forEach(d => d.classList.remove('open'));
        if (!wasOpen) dd.classList.add('open');
        return;
    }

    // 7. Click bahar — dropdowns band
    if (!e.target.closest('.size-dropdown')) {
        document.querySelectorAll('.size-dropdown.open').forEach(d => d.classList.remove('open'));
    }
});

// Scroll pe band
document.addEventListener('scroll', function() {
    document.querySelectorAll('.size-dropdown.open').forEach(d => d.classList.remove('open'));
}, true);

// ─────────────────────────────────────────
// ADD ITEM (dono sized + non-sized)
// ─────────────────────────────────────────
function addItem(dishName, sizeLabel, sizePrice, ddid, idx) {
    // Non-sized ka key = dishName, sized ka = "dishName (label)"
    const key = sizeLabel ? dishName + ' (' + sizeLabel + ')' : dishName;
    const displayName = sizeLabel ? dishName + ' (' + sizeLabel + ')' : dishName;

    if (plate[key]) {
        plate[key].qty += 1;
    } else {
        plate[key] = {
            qty: 1,
            price: sizePrice,
            displayName: displayName,
            baseName: dishName,
            ddid: ddid,
            idx: idx
        };
    }
    updateCtrl(ddid, idx, dishName, sizeLabel, sizePrice, plate[key].qty);
    updateCardBadge(dishName);
    renderDrawer();
    updateTotals();
    savePlateToStorage();
}

// ─────────────────────────────────────────
// REMOVE ITEM from dropdown
// ─────────────────────────────────────────
function removeItem(dishName, sizeLabel, ddid, idx) {
    const key = sizeLabel ? dishName + ' (' + sizeLabel + ')' : dishName;
    if (!plate[key]) return;
    plate[key].qty -= 1;
    const qty = plate[key].qty;
    const price = plate[key].price;
    if (qty <= 0) {
        delete plate[key];
        Object.keys(keyMap).forEach(k => { if (keyMap[k] === key) delete keyMap[k]; });
    }
    updateCtrl(ddid, idx, dishName, sizeLabel, price, qty <= 0 ? 0 : qty);
    updateCardBadge(dishName);
    renderDrawer();
    updateTotals();
    savePlateToStorage();
}

// ─────────────────────────────────────────
// DRAWER QTY CHANGE — + visual update karo
// ─────────────────────────────────────────
function drawerChangeQty(key, delta) {
    if (!plate[key]) return;
    const { baseName, ddid, idx, price } = plate[key];
    const sizeLabel = plate[key].displayName !== baseName
        ? plate[key].displayName.replace(baseName + ' (', '').replace(')', '')
        : '';

    plate[key].qty += delta;
    const qty = plate[key].qty;

    if (qty <= 0) {
        delete plate[key];
        Object.keys(keyMap).forEach(k => { if (keyMap[k] === key) delete keyMap[k]; });
        updateCtrl(ddid, idx, baseName, sizeLabel, price, 0);
    } else {
        updateCtrl(ddid, idx, baseName, sizeLabel, price, qty);
    }

    updateCardBadge(baseName);
    renderDrawer();
    updateTotals();
    savePlateToStorage();
}

// ─────────────────────────────────────────
// UPDATE DROPDOWN ROW CTRL
// ─────────────────────────────────────────
function updateCtrl(ddid, idx, dishName, sizeLabel, sizePrice, qty) {
    const ctrlDiv = document.getElementById('ctrl-' + ddid + '-' + idx);
    if (!ctrlDiv) return;
    if (qty <= 0) {
        ctrlDiv.innerHTML =
            '<button class="qty-btn js-size-add"' +
            ' data-dish="' + dishName + '"' +
            ' data-label="' + sizeLabel + '"' +
            ' data-price="' + sizePrice + '"' +
            ' data-ddid="' + ddid + '"' +
            ' data-idx="' + idx + '">+</button>';
    } else {
        ctrlDiv.innerHTML =
            '<button class="qty-btn js-size-minus"' +
            ' data-dish="' + dishName + '"' +
            ' data-label="' + sizeLabel + '"' +
            ' data-ddid="' + ddid + '"' +
            ' data-idx="' + idx + '">−</button>' +
            '<span class="qty-num">' + qty + '</span>' +
            '<button class="qty-btn js-size-add"' +
            ' data-dish="' + dishName + '"' +
            ' data-label="' + sizeLabel + '"' +
            ' data-price="' + sizePrice + '"' +
            ' data-ddid="' + ddid + '"' +
            ' data-idx="' + idx + '">+</button>';
    }
}

// ─────────────────────────────────────────
// CARD BADGE — total qty dikhao + button pe
// ─────────────────────────────────────────
function updateCardBadge(dishName) {
    const card = findCard(dishName);
    if (!card) return;
    const ddid = card.dataset.ddid;
    const wrapper = document.getElementById('abw-' + ddid);
    if (!wrapper) return;

    const totalQty = Object.values(plate)
        .filter(v => v.baseName === dishName)
        .reduce((s, v) => s + v.qty, 0);

    const toggleBtn = wrapper.querySelector('.js-size-toggle');
    let badge = wrapper.querySelector('.size-total-badge');

    if (totalQty > 0) {
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'size-total-badge';
            wrapper.appendChild(badge);
        }
        badge.textContent = totalQty;
        if (toggleBtn) toggleBtn.style.cssText = 'background:var(--secondary);color:white';
    } else {
        if (badge) badge.remove();
        if (toggleBtn) toggleBtn.style.cssText = '';
    }
}

// ─────────────────────────────────────────
// DRAWER RENDER
// ─────────────────────────────────────────
function renderDrawer() {
    var items = Object.entries(plate);
    var container = document.getElementById('drawer-items');

    if (!items.length) {
        container.innerHTML = '<div class="empty-plate"><i class="fas fa-utensils"></i>Your plate is empty</div>';
        return;
    }

    container.innerHTML = items.map(function(entry) {
        var key = entry[0], v = entry[1];
        var safeK = 'dr_' + sk(key);
        keyMap[safeK] = key;
        return '<div class="drawer-item">' +
            '<div class="qty-controls">' +
            '<button class="qty-btn js-qty" data-sk="' + safeK + '" data-delta="-1">−</button>' +
            '<span class="qty-num">' + v.qty + '</span>' +
            '<button class="qty-btn js-qty" data-sk="' + safeK + '" data-delta="1">+</button>' +
            '</div>' +
            '<div class="drawer-item-name">' + v.displayName + '</div>' +
            '<div class="drawer-item-price">INR ' + (parsePrice(v.price) * v.qty) + '</div>' +
            '</div>';
    }).join('');
}

// ─────────────────────────────────────────
// TOTALS
// ─────────────────────────────────────────
function updateTotals() {
    var items = Object.entries(plate);
    var totalQty   = items.reduce(function(s, e) { return s + e[1].qty; }, 0);
    var totalPrice = items.reduce(function(s, e) { return s + parsePrice(e[1].price) * e[1].qty; }, 0);

    // plate-count aur plate-total — dono jagah hain (dine-in btn + delivery cw-bar)
    document.querySelectorAll('#plate-count').forEach(function(el) {
        el.textContent = totalQty;
    });
    document.querySelectorAll('#plate-total').forEach(function(el) {
        el.textContent = totalQty > 0 ? '• INR ' + totalPrice : '';
    });
    document.getElementById('drawer-total-price').textContent = 'INR ' + totalPrice;

    // Dine-in plate-btn
    var plateBtn = document.getElementById('plate-btn');
    if (plateBtn) plateBtn.classList.toggle('visible', totalQty > 0);

    // Delivery mode — cw-bar morph
    var cwBar = document.getElementById('cw-bar');
    if (cwBar) {
        if (totalQty > 0) {
            cwBar.classList.remove('state-profile');
            cwBar.classList.add('state-plate');
        } else {
            cwBar.classList.remove('state-plate');
            cwBar.classList.add('state-profile');
        }
    }
}

// ─────────────────────────────────────────
// DRAWER TOGGLE
// ─────────────────────────────────────────
var drawerOpen = false;
function toggleDrawer() {
    drawerOpen = !drawerOpen;
    document.getElementById('plate-drawer').classList.toggle('open', drawerOpen);
    document.getElementById('overlay').classList.toggle('show', drawerOpen);
}

// ─────────────────────────────────────────
// TABS
// ─────────────────────────────────────────
document.getElementById('tabs').addEventListener('click', function(e) {
    var tab = e.target.closest('.tab');
    if (!tab) return;
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    tab.classList.add('active');
    var cat = tab.dataset.cat;
    document.querySelectorAll('.category-section').forEach(function(s) {
        s.style.display = (cat === 'all' || s.dataset.section === cat) ? 'block' : 'none';
    });
});

// ─────────────────────────────────────────
// PLACE ORDER
// ─────────────────────────────────────────
async function placeOrder() {
    var entries = Object.entries(plate);
    if (!entries.length) return;

    // Delivery flow — TABLE_NO nahi hai
    if (!TABLE_NO) {
        await handleDeliveryOrder();
        return;
    }

    // Normal dine-in flow
    await submitOrder({ table_no: TABLE_NO });
}

// ─────────────────────────────────────────
// DELIVERY FLOW
// ─────────────────────────────────────────
async function handleDeliveryOrder() {
    // Step 1 — customer logged in hai?
    var me = await fetch('/api/customer/me').then(r => r.json());

    if (!me.logged_in) {
        // Login nahi hai — Google login pe bhejo, wapas is page pe aana
        const searchSep = window.location.search ? '&' : '?';
        const nextUrl = window.location.pathname + window.location.search + searchSep + 'trigger_delivery=true';
        const next = encodeURIComponent(nextUrl);
        window.location.href = '/auth/google?next=' + next;
        return;
    }

    if (!me.profile_complete) {
        // Phone/address missing — profile page pe bhejo
        const searchSep = window.location.search ? '&' : '?';
        const nextUrl = window.location.pathname + window.location.search + searchSep + 'trigger_delivery=true';
        const next = encodeURIComponent(nextUrl);
        window.location.href = '/customer/profile?next=' + next;
        return;
    }

    // Step 2 — address confirm modal dikhao
    showDeliveryConfirmModal(me);
}

function showDeliveryConfirmModal(customer) {
    // Purana modal hatao agar hai
    var old = document.getElementById('delivery-confirm-modal');
    if (old) old.remove();

    var modal = document.createElement('div');
    modal.id = 'delivery-confirm-modal';
    modal.style.cssText = [
        'position:fixed', 'inset:0', 'z-index:1000',
        'display:flex', 'align-items:center', 'justify-content:center',
        'background:rgba(0,0,0,0.5)', 'padding:16px'
    ].join(';');

    modal.innerHTML = [
        '<div style="background:white;border-radius:16px;padding:24px;width:100%;max-width:420px;box-shadow:0 8px 30px rgba(0,0,0,0.2)">',
            '<h3 style="margin:0 0 4px;font-size:1.1rem">🛵 Confirm Delivery</h3>',
            '<p style="margin:0 0 16px;font-size:0.85rem;color:#666">Details check karo aur order place karo</p>',

            '<div style="background:#f8f8f8;border-radius:10px;padding:14px;margin-bottom:16px;font-size:0.9rem">',
                '<div style="margin-bottom:6px"><b>👤 Name:</b> ' + customer.name + '</div>',
                '<div style="margin-bottom:6px"><b>📞 Phone:</b> ' + customer.phone + '</div>',
                '<div><b>📍 Address:</b> ' + customer.address + '</div>',
            '</div>',

            '<div style="display:flex;gap:8px;justify-content:flex-end">',
                '<button onclick="changeDeliveryAddress()" style="padding:10px 16px;border:1px solid #ddd;border-radius:8px;background:white;cursor:pointer;font-size:0.9rem">',
                    'Change Address',
                '</button>',
                '<button onclick="confirmDeliveryOrder()" style="padding:10px 20px;border:none;border-radius:8px;background:var(--secondary,#222);color:white;cursor:pointer;font-size:0.9rem;font-weight:600">',
                    'Place Order →',
                '</button>',
            '</div>',
        '</div>'
    ].join('');

    document.body.appendChild(modal);

    // Bahar click pe band
    modal.addEventListener('click', function(e) {
        if (e.target === modal) modal.remove();
    });
}

function changeDeliveryAddress() {
    var modal = document.getElementById('delivery-confirm-modal');
    if (modal) modal.remove();
    const searchSep = window.location.search ? '&' : '?';
    const nextUrl = window.location.pathname + window.location.search + searchSep + 'trigger_delivery=true';
    const next = encodeURIComponent(nextUrl);
    window.location.href = '/customer/profile?next=' + next;
}

async function confirmDeliveryOrder() {
    var btn = document.querySelector('#delivery-confirm-modal button:last-child');
    if (btn) { btn.disabled = true; btn.textContent = 'Placing...'; }

    var me = await fetch('/api/customer/me').then(r => r.json());
    await submitOrder({
        table_no:         0,
        source:           'delivery',
        customer_address: me.address,
        customer_name:    me.name,
        customer_phone:   me.phone,
    });

    var modal = document.getElementById('delivery-confirm-modal');
    if (modal) modal.remove();
}

// ─────────────────────────────────────────
// SUBMIT ORDER — dine-in + delivery dono
// ─────────────────────────────────────────
async function submitOrder(extra) {
    var entries = Object.entries(plate);
    var items = entries.map(function(e) {
        return { name: e[1].displayName, qty: e[1].qty, price: parsePrice(e[1].price) };
    });
    var total = items.reduce(function(s, i) { return s + i.qty * i.price; }, 0);

    var tableNo  = (extra.table_no !== undefined) ? extra.table_no : TABLE_NO;
    var branchQ  = (typeof BRANCH_ID !== 'undefined' && BRANCH_ID && BRANCH_ID !== '__default__') ? '?branch_id=' + BRANCH_ID : '';
    var body     = Object.assign({ items: items, total: total }, extra);

    var res = await fetch('/api/order/' + CLIENT_ID + '/' + tableNo + branchQ, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body)
    });

    if (res.ok) {
        // Cart reset
        Object.keys(plate).forEach(function(k) { delete plate[k]; });
        Object.keys(keyMap).forEach(function(k) { delete keyMap[k]; });
        savePlateToStorage();

        // Sab cards reset
        document.querySelectorAll('.dish-card').forEach(function(card) {
            var ddid = card.dataset.ddid;
            var wrapper = document.getElementById('abw-' + ddid);
            if (wrapper) {
                var badge = wrapper.querySelector('.size-total-badge');
                if (badge) badge.remove();
                var btn = wrapper.querySelector('.js-size-toggle');
                if (btn) btn.style.cssText = '';
            }
            var dd = document.getElementById(ddid);
            if (dd) {
                dd.querySelectorAll('.size-row-ctrl').forEach(function(ctrl) {
                    var addBtn = ctrl.querySelector('.js-size-add');
                    if (addBtn) {
                        ctrl.innerHTML =
                            '<button class="qty-btn js-size-add"' +
                            ' data-dish="' + addBtn.dataset.dish + '"' +
                            ' data-label="' + addBtn.dataset.label + '"' +
                            ' data-price="' + addBtn.dataset.price + '"' +
                            ' data-ddid="' + addBtn.dataset.ddid + '"' +
                            ' data-idx="' + addBtn.dataset.idx + '">+</button>';
                    }
                });
                dd.classList.remove('open');
            }
        });

        renderDrawer();
        updateTotals();
        if (drawerOpen) toggleDrawer();

        var isDelivery = extra.source === 'delivery';
        var msg = document.createElement('div');
        msg.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--secondary);color:white;padding:20px 32px;border-radius:16px;font-size:1rem;font-weight:600;z-index:9999;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,0.3)';
        msg.innerHTML = isDelivery
            ? '✅ Order placed!<br><small style="opacity:0.7;font-weight:400">🛵 Delivery on the way</small>'
            : '✅ Order placed!<br><small style="opacity:0.7;font-weight:400">Table ' + TABLE_NO + '</small>';
        document.body.appendChild(msg);
        setTimeout(function() { msg.remove(); }, 2500);
    } else {
        var err = await res.json();
        var errMsg = 'Something went wrong';
        if (err.detail) {
            if (typeof err.detail === 'string') {
                errMsg = err.detail;
            } else if (Array.isArray(err.detail)) {
                errMsg = err.detail.map(function(d) { return d.msg; }).join(', ');
            } else if (typeof err.detail === 'object') {
                errMsg = JSON.stringify(err.detail);
            }
        }
        alert('❌ ' + errMsg);
    }
}

// Load cart on initialization
loadPlateFromStorage();

// Auto-trigger delivery modal if returning from auth/profile
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('trigger_delivery') === 'true') {
    // URL se trigger_delivery ko bina refresh clean karo
    const cleanSearch = window.location.search.replace(/[?&]trigger_delivery=true/, '');
    const cleanUrl = window.location.pathname + cleanSearch;
    window.history.replaceState({}, document.title, cleanUrl);

    if (Object.keys(plate).length > 0) {
        if (!drawerOpen) toggleDrawer();
        handleDeliveryOrder();
    }
}
