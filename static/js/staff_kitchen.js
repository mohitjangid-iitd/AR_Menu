// clientId, restaurantLogo — HTML template mein inject hote hain

async function updateStatus(orderId, status) {
    const res = await fetch(`/api/order/${orderId}/status`, {
        method: 'PATCH',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ status })
    });
    if (res.ok) {
        toast(`Order #${orderId} → ${status}`);
        if (status === 'ready') load();
    }
}

function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg; t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
}

// ── NOTIFICATIONS ──
let notifPermission = Notification.permission;
let knownOrderIds = new Set();
let firstLoad = true;

async function requestNotifPermission() {
    if (notifPermission === 'default') {
        notifPermission = await Notification.requestPermission();
    }
}

function sendNotif(title, body) {
    if (notifPermission === 'granted') {
        const n = new Notification(title, {
            body,
            icon: restaurantLogo,
            badge: restaurantLogo,
            tag: 'kitchen-order',
            requireInteraction: true
        });
        n.onclick = () => { window.focus(); n.close(); };
    }
}

async function loadWithNotif() {
    const res = await fetch(`/api/orders/${clientId}`);
    const orders = await res.json();
    const active = orders.filter(o => !['done','cancelled'].includes(o.status));

    if (!firstLoad) {
        const newPending = active.filter(o => o.status === 'pending' && !knownOrderIds.has(o.id));
        if (newPending.length > 0) {
            const tables = [...new Set(newPending.map(o => o.table_no))].join(', ');
            sendNotif(
                `🔥 ${newPending.length} New Order${newPending.length>1?'s':''}!`,
                `Table${newPending.length>1?'s':''} ${tables} — tap to view`
            );
            // Play a beep
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                osc.frequency.value = 880;
                osc.type = 'sine';
                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.4);
            } catch(e) {}
        }
    }

    active.forEach(o => knownOrderIds.add(o.id));
    firstLoad = false;

    const list = document.getElementById('orders-list');
    if (!active.length) {
        list.innerHTML = `<div class="empty-state">
            <i class="fas fa-check-circle" style="color:#4caf50"></i>
            <p>No pending orders!</p>
        </div>`;
        return;
    }
    list.innerHTML = active.map(o => {
        const items = typeof o.items === 'string' ? JSON.parse(o.items) : o.items;
        const time = (o.created_at || '').substring(11, 16);
        return `<div class="order-card ${o.status}">
            <div class="order-head">
                <div>
                    <div class="order-table">Table ${o.table_no}</div>
                    <div class="order-id">#${o.id} &nbsp;·&nbsp; ${o.source}</div>
                </div>
                <div class="order-time">${time}</div>
            </div>
            <div class="order-items">
                ${items.map(i => `
                    <div class="order-item-row">
                        <span class="item-name">${i.name}</span>
                        <span class="item-qty">×${i.qty}</span>
                    </div>`).join('')}
            </div>
            <div class="order-foot">
                <div class="order-total">₹${o.total}</div>
                <select class="status-select" onchange="updateStatus(${o.id}, this.value)">
                    <option value="pending"   ${o.status==='pending'   ?'selected':''}>⏳ Pending</option>
                    <option value="preparing" ${o.status==='preparing' ?'selected':''}>👨‍🍳 Preparing</option>
                    <option value="ready"     ${o.status==='ready'     ?'selected':''}>✅ Ready</option>
                </select>
            </div>
        </div>`;
    }).join('');
}

// Notif permission button
const topbar = document.querySelector('.topbar > div:last-child');
const notifBtn = document.createElement('button');
notifBtn.className = 'logout-btn';
notifBtn.id = 'notif-btn';
notifBtn.innerHTML = '🔔 Alerts';
notifBtn.onclick = async () => {
    await requestNotifPermission();
    notifBtn.innerHTML = notifPermission === 'granted' ? '🔔 On' : '🔕 Off';
    toast(notifPermission === 'granted' ? '✅ Notifications enabled!' : '❌ Notifications blocked');
};
topbar.insertBefore(notifBtn, topbar.firstChild);
if (notifPermission === 'granted') notifBtn.innerHTML = '🔔 On';

// load function
async function load() { await loadWithNotif(); }

// Init + auto refresh every 20s
requestNotifPermission();
load();
setInterval(load, 20000);
