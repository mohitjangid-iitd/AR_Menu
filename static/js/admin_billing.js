// ════════════════════════════════
// ADMIN BILLING — admin_billing.js
// ════════════════════════════════

const Billing = (() => {

    // ── State ──
    let _allSubs   = [];
    let _plans     = [];
    let _addons    = [];
    let _filter    = 'all';
    let _activeSub = null;   // modal mein khula hua subscription

    // ── Status config ──
    const STATUS = {
        demo:    { label: 'Demo',    color: '#4dabf7', bg: 'rgba(77,171,247,0.12)' },
        trial:   { label: 'Trial',   color: '#ffb347', bg: 'rgba(255,179,71,0.12)' },
        active:  { label: 'Active',  color: '#43e97b', bg: 'rgba(67,233,123,0.12)' },
        grace:   { label: 'Grace',   color: '#ff6b6b', bg: 'rgba(255,107,107,0.12)' },
        expired: { label: 'Expired', color: '#888',    bg: 'rgba(136,136,136,0.12)' },
    };

    const PERIOD_LABEL = { monthly: 'Monthly', halfyearly: 'Half-yearly', yearly: 'Yearly' };

    // ════════════════════════════════
    // LOAD
    // ════════════════════════════════

    async function load() {
        document.getElementById('billing-list').innerHTML =
            '<div class="loading">Loading...</div>';
        try {
            const res  = await fetch('/api/billing/subscriptions', { credentials: 'include' });
            const data = await res.json();
            _allSubs = data.subscriptions || [];
            _plans   = data.plans   || [];
            _addons  = data.addons  || [];
            render();
        } catch (e) {
            document.getElementById('billing-list').innerHTML =
                '<div class="empty">Load failed — ' + e.message + '</div>';
        }
    }

    // ════════════════════════════════
    // RENDER — subscription cards
    // ════════════════════════════════

    function render() {
        const list = document.getElementById('billing-list');
        let subs = _allSubs;
        if (_filter !== 'all') subs = subs.filter(s => s.status === _filter);

        if (!subs.length) {
            list.innerHTML = '<div class="empty" style="padding:32px;text-align:center;color:var(--muted);">Koi subscription nahi mili</div>';
            return;
        }

        list.innerHTML = `
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;">
                ${subs.map(s => cardHTML(s)).join('')}
            </div>
        `;
    }

    function cardHTML(sub) {
        const st    = STATUS[sub.status] || STATUS.expired;
        const pLabel = PERIOD_LABEL[sub.period] || sub.period || '—';
        const plan  = _plans.find(p => p.key === sub.plan_key);
        const planName = plan ? plan.name : (sub.plan_key || '—');

        // Expiry date determine karo
        let expiryLabel = '';
        if (sub.status === 'demo') {
            expiryLabel = 'Never expires';
        } else if (sub.status === 'trial' && sub.trial_ends_at) {
            expiryLabel = 'Trial ends: ' + sub.trial_ends_at;
        } else if (sub.current_period_ends_at) {
            expiryLabel = 'Renews: ' + sub.current_period_ends_at;
        }

        return `
        <div class="card" style="cursor:pointer;transition:border-color .15s;"
             onmouseenter="this.style.borderColor='rgba(108,99,255,0.4)'"
             onmouseleave="this.style.borderColor=''"
             onclick="Billing.openModal('${sub.client_id}')">
            <div class="card-body" style="display:flex;flex-direction:column;gap:10px;">

                <div style="display:flex;align-items:center;justify-content:space-between;">
                    <div style="font-size:0.95rem;font-weight:700;color:white;">${sub.client_id}</div>
                    <span style="font-size:0.7rem;font-weight:600;padding:3px 10px;border-radius:20px;
                        color:${st.color};background:${st.bg};border:1px solid ${st.color}33;">
                        ${st.label}
                    </span>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                    <div style="font-size:0.75rem;color:var(--muted);">Plan</div>
                    <div style="font-size:0.75rem;color:white;font-weight:600;">${planName}</div>
                    <div style="font-size:0.75rem;color:var(--muted);">Period</div>
                    <div style="font-size:0.75rem;color:white;">${pLabel}</div>
                    <div style="font-size:0.75rem;color:var(--muted);">Amount</div>
                    <div style="font-size:0.75rem;color:white;font-weight:600;">
                        ${sub.final_price ? '₹' + sub.final_price.toLocaleString() : '—'}
                        ${sub.discount_percent || sub.discount_flat ?
                            `<span style="color:#43e97b;font-size:0.65rem;margin-left:4px;">
                                ${sub.discount_percent ? sub.discount_percent + '% off' : ''}
                                ${sub.discount_flat ? '₹' + sub.discount_flat + ' off' : ''}
                            </span>` : ''}
                    </div>
                    <div style="font-size:0.75rem;color:var(--muted);">Expiry</div>
                    <div style="font-size:0.75rem;color:var(--muted);">${expiryLabel || '—'}</div>
                </div>

                <div style="display:flex;gap:6px;margin-top:4px;">
                    <button onclick="event.stopPropagation();Billing.openConfirmPayment('${sub.client_id}')"
                        style="flex:1;padding:6px;border-radius:6px;border:1px solid var(--border);
                               background:rgba(67,233,123,0.08);color:#43e97b;font-size:0.72rem;cursor:pointer;">
                        ✓ Confirm Payment
                    </button>
                    <button onclick="event.stopPropagation();Billing.openModal('${sub.client_id}')"
                        style="flex:1;padding:6px;border-radius:6px;border:1px solid var(--border);
                               background:transparent;color:var(--muted);font-size:0.72rem;cursor:pointer;">
                        ✎ Edit
                    </button>
                </div>

            </div>
        </div>`;
    }

    // ════════════════════════════════
    // FILTER
    // ════════════════════════════════

    function setFilter(f, el) {
        _filter = f;
        document.querySelectorAll('#tab-billing .filter-pill')
            .forEach(b => b.classList.remove('active'));
        if (el) el.classList.add('active');
        render();
    }

    // ════════════════════════════════
    // MODAL — subscription detail + edit
    // ════════════════════════════════

    async function openModal(clientId) {
        _activeSub = null;
        _ensureModal();
        document.getElementById('bm-overlay').style.display = 'flex';
        document.getElementById('bm-body').innerHTML =
            '<div class="loading" style="padding:32px;">Loading...</div>';
        document.getElementById('bm-title').textContent = clientId;

        try {
            const res  = await fetch(`/api/billing/subscriptions/${clientId}`, { credentials: 'include' });
            if (!res.ok) {
                if (res.status === 404) {
                    document.getElementById('bm-body').innerHTML = `
                        <div class="empty" style="padding:32px;text-align:center;">
                            <div style="margin-bottom:16px;color:var(--muted);">Is restaurant ki koi active subscription nahi hai.</div>
                            <button class="btn btn-primary" onclick="Billing.closeModal(); Billing.createForRestaurant('${clientId}')">
                                + Create Subscription
                            </button>
                        </div>`;
                    return;
                }
                throw new Error(await res.text());
            }
            const data = await res.json();
            _activeSub = data;
            _renderModal(data);
        } catch (e) {
            document.getElementById('bm-body').innerHTML =
                '<div class="empty">Load failed — ' + e.message + '</div>';
        }
    }

    function closeModal() {
        const ov = document.getElementById('bm-overlay');
        if (ov) ov.style.display = 'none';
        _activeSub = null;
    }

    function _renderModal(data) {
        const sub    = data.subscription;
        const addons = data.addons   || [];
        const hist   = data.history  || [];
        const refId  = data.ref_id   || '';

        const st       = STATUS[sub.status] || STATUS.expired;
        const planOpts = _plans.map(p =>
            `<option value="${p.key}" ${p.key === sub.plan_key ? 'selected' : ''}>${p.name} — ₹${p.monthly_price}/mo</option>`
        ).join('');

        document.getElementById('bm-body').innerHTML = `

        <!-- ── Status + Plan ── -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
            <div class="form-group" style="margin:0;">
                <label>Status</label>
                <select id="bm-status" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;" onchange="Billing._onStatusChange(this.value)">
                    <option value="demo"    ${sub.status==='demo'    ? 'selected':''}>Demo</option>
                    <option value="trial"   ${sub.status==='trial'   ? 'selected':''}>Trial</option>
                    <option value="active"  ${sub.status==='active'  ? 'selected':''}>Active</option>
                    <option value="grace"   ${sub.status==='grace'   ? 'selected':''}>Grace</option>
                    <option value="expired" ${sub.status==='expired' ? 'selected':''}>Expired</option>
                </select>
            </div>
            <div class="form-group" style="margin:0;">
                <label>Plan</label>
                <select id="bm-plan" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;" onchange="Billing._refreshPreview()">
                    ${planOpts}
                </select>
            </div>
        </div>

        <!-- ── Period + Discounts ── -->
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px;">
            <div class="form-group" style="margin:0;">
                <label>Period</label>
                <select id="bm-period" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;" onchange="Billing._refreshPreview()">
                    <option value="monthly"    ${sub.period==='monthly'    ? 'selected':''}>Monthly</option>
                    <option value="halfyearly" ${sub.period==='halfyearly' ? 'selected':''}>Half-yearly</option>
                    <option value="yearly"     ${sub.period==='yearly'     ? 'selected':''}>Yearly</option>
                </select>
            </div>
            <div class="form-group" style="margin:0;">
                <label>Discount %</label>
                <input type="number" id="bm-dpct" value="${sub.discount_percent || 0}" min="0" max="100"
                    style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;"
                    oninput="Billing._refreshPreview()">
            </div>
            <div class="form-group" style="margin:0;">
                <label>Discount ₹ flat</label>
                <input type="number" id="bm-dflat" value="${sub.discount_flat || 0}" min="0"
                    style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;"
                    oninput="Billing._refreshPreview()">
            </div>
        </div>

        <!-- ── Price preview ── -->
        <div id="bm-price-preview" style="background:rgba(108,99,255,0.07);border:1px solid rgba(108,99,255,0.2);border-radius:10px;padding:12px 16px;margin-bottom:16px;font-size:0.8rem;color:var(--muted);">
            Calculating...
        </div>

        <!-- ── Dates (status active hone pe dikhega) ── -->
        <div id="bm-dates-section" style="display:${['active','grace'].includes(sub.status) ? '' : 'none'};">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
                <div class="form-group" style="margin:0;">
                    <label>Period Ends At</label>
                    <input type="date" id="bm-period-end" value="${sub.current_period_ends_at || ''}"
                        style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                </div>
                <div class="form-group" style="margin:0;">
                    <label>Trial Ends At</label>
                    <input type="date" id="bm-trial-end" value="${sub.trial_ends_at === '9999-12-31' ? '' : (sub.trial_ends_at || '')}"
                        style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                </div>
            </div>
        </div>

        <!-- ── Add-ons ── -->
        <div style="margin-bottom:16px;">
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:10px;">Add-ons</div>
            <div style="display:flex;flex-direction:column;gap:8px;" id="bm-addons-list">
                ${_addons.map(a => {
                    const active = addons.find(sa => sa.addon_key === a.key && sa.is_active);
                    return `
                    <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,0.02);">
                        <div>
                            <div style="font-size:0.82rem;font-weight:600;color:white;">${a.name}</div>
                            <div style="font-size:0.7rem;color:var(--muted);">${a.one_time_only ? 'One-time' : '₹'+a.monthly_price+'/mo'}</div>
                        </div>
                        ${active
                            ? `<button onclick="Billing.removeAddon('${sub.client_id}','${a.key}')"
                                style="font-size:0.7rem;padding:4px 10px;border-radius:6px;border:1px solid rgba(255,71,87,0.3);background:rgba(255,71,87,0.08);color:#ff4757;cursor:pointer;">
                                Remove</button>`
                            : `<button onclick="Billing.addAddon('${sub.client_id}','${a.key}')"
                                style="font-size:0.7rem;padding:4px 10px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;">
                                + Add</button>`
                        }
                    </div>`;
                }).join('')}
            </div>
        </div>

        <!-- ── Notes ── -->
        <div class="form-group" style="margin-bottom:16px;">
            <label>Admin Notes</label>
            <textarea id="bm-notes" rows="2"
                style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;resize:vertical;font-size:0.82rem;"
                placeholder="Internal notes...">${sub.admin_notes || ''}</textarea>
        </div>

        <!-- ── Payment History ── -->
        <div>
            <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:10px;">
                Payment History
                <span style="margin-left:8px;font-size:0.7rem;color:var(--primary);font-family:var(--font-m);">Ref: ${refId}</span>
            </div>
            ${hist.length ? `
            <div style="border:1px solid var(--border);border-radius:8px;overflow:hidden;">
                <table class="data-table" style="margin:0;">
                    <thead><tr>
                        <th>Date</th><th>Amount</th><th>Mode</th><th>Status</th><th>By</th>
                    </tr></thead>
                    <tbody>
                        ${hist.map(h => `
                        <tr>
                            <td style="font-size:0.75rem;">${(h.created_at||'').slice(0,10)}</td>
                            <td style="font-size:0.75rem;font-weight:600;">₹${(h.amount||0).toLocaleString()}</td>
                            <td style="font-size:0.75rem;">${h.payment_mode||'—'}</td>
                            <td style="font-size:0.75rem;">
                                <span style="color:${h.status==='confirmed'?'#43e97b':'#ffb347'};">${h.status}</span>
                            </td>
                            <td style="font-size:0.75rem;color:var(--muted);">${h.confirmed_by||'—'}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            </div>` : '<div style="font-size:0.8rem;color:var(--muted);padding:8px 0;">Koi payment nahi abhi tak</div>'}
        </div>
        `;

        // Price preview fetch
        _refreshPreview();
    }

    // ── Status change → dates section toggle ──
    function _onStatusChange(val) {
        const ds = document.getElementById('bm-dates-section');
        if (ds) ds.style.display = ['active','grace'].includes(val) ? '' : 'none';
        _refreshPreview();
    }

    // ── Live price preview ──
    async function _refreshPreview() {
        const plan   = document.getElementById('bm-plan')?.value   || 'basic';
        const period = document.getElementById('bm-period')?.value  || 'monthly';
        const dpct   = document.getElementById('bm-dpct')?.value    || 0;
        const dflat  = document.getElementById('bm-dflat')?.value   || 0;
        const el     = document.getElementById('bm-price-preview');
        if (!el) return;

        try {
            const res  = await fetch(
                `/api/billing/preview-price?plan_key=${plan}&period=${period}&discount_percent=${dpct}&discount_flat=${dflat}`,
                { credentials: 'include' }
            );
            const data = await res.json();
            const p    = data.plan;
            const mLabel = { monthly:'Monthly', halfyearly:'Half-yearly (5×)', yearly:'Yearly (10×)' };
            el.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <div>
                        <span style="color:var(--muted);">Base (${mLabel[period]||period}):</span>
                        <span style="color:white;font-weight:600;margin-left:6px;">₹${p.base_price.toLocaleString()}</span>
                        ${p.discount_flat ? `<span style="color:#43e97b;margin-left:6px;">− ₹${p.discount_flat}</span>` : ''}
                        ${p.discount_percent ? `<span style="color:#43e97b;margin-left:6px;">− ${p.discount_percent}%</span>` : ''}
                    </div>
                    <div style="font-size:1.1rem;font-weight:700;color:white;">
                        Final: ₹${data.grand_total.toLocaleString()}
                        <span style="font-size:0.7rem;color:var(--muted);font-weight:400;">/${period}</span>
                    </div>
                </div>
            `;
        } catch (e) {
            el.textContent = 'Preview load failed';
        }
    }

    // ── Save subscription ──
    async function save() {
        if (!_activeSub) return;
        const clientId = _activeSub.subscription.client_id;
        const payload  = {
            status:                 document.getElementById('bm-status')?.value,
            plan_key:               document.getElementById('bm-plan')?.value,
            period:                 document.getElementById('bm-period')?.value,
            discount_percent:       parseInt(document.getElementById('bm-dpct')?.value || 0),
            discount_flat:          parseInt(document.getElementById('bm-dflat')?.value || 0),
            current_period_ends_at: document.getElementById('bm-period-end')?.value || null,
            trial_ends_at:          document.getElementById('bm-trial-end')?.value || null,
            admin_notes:            document.getElementById('bm-notes')?.value || null,
        };

        try {
            const res = await fetch(`/api/billing/subscriptions/${clientId}`, {
                method: 'PATCH', credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(await res.text());
            showToast('Subscription updated ✓', 'success');
            closeModal();
            load();
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    }

    // ════════════════════════════════
    // CONFIRM PAYMENT MODAL
    // ════════════════════════════════

    async function openConfirmPayment(clientId) {
        _ensurePayModal();
        document.getElementById('bpm-overlay').style.display = 'flex';
        document.getElementById('bpm-client-id').textContent = clientId;
        document.getElementById('bpm-cid').value = clientId;

        // UPI data fetch karo
        try {
            const res  = await fetch(`/api/billing/subscriptions/${clientId}/upi-data`, { credentials: 'include' });
            const data = await res.json();
            document.getElementById('bpm-amount').value  = data.amount || '';
            document.getElementById('bpm-ref').value     = data.reference_id || '';
            document.getElementById('bpm-upi-str').textContent = data.upi_string || '';

            // QR generate karo — qrcodejs library se (CDN)
            const qrEl = document.getElementById('bpm-qr');
            qrEl.innerHTML = '';
            
            const renderQR = () => {
                qrEl.innerHTML = '';
                new QRCode(qrEl, {
                    text: data.upi_string,
                    width: 160, height: 160,
                    colorDark: '#fff', colorLight: '#1a1a2e',
                });
            };

            if (data.upi_string) {
                if (window.QRCode) {
                    renderQR();
                } else {
                    qrEl.innerHTML = '<div style="font-size:0.75rem;color:var(--muted);">QR Code loading...</div>';
                    // Find or wait for the script to load
                    const script = document.querySelector('script[src*="qrcode.min.js"]');
                    if (script) {
                        script.addEventListener('load', renderQR);
                    } else {
                        // In case script tag wasn't created yet or we need to add it
                        const s = document.createElement('script');
                        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
                        s.onload = renderQR;
                        document.head.appendChild(s);
                    }
                }
            }

            // Sub ki period bhi set karo
            const sRes = await fetch(`/api/billing/subscriptions/${clientId}`, { credentials: 'include' });
            const sData = await sRes.json();
            const period = sData.subscription?.period || 'monthly';
            document.getElementById('bpm-period').value = period;
        } catch (e) {
            showToast('UPI data load failed', 'error');
        }
    }

    function closePayModal() {
        const ov = document.getElementById('bpm-overlay');
        if (ov) ov.style.display = 'none';
    }

    async function submitConfirmPayment() {
        const clientId = document.getElementById('bpm-cid').value;
        const payload  = {
            amount:       parseInt(document.getElementById('bpm-amount').value),
            period:       document.getElementById('bpm-period').value,
            payment_mode: document.getElementById('bpm-mode').value,
            reference_id: document.getElementById('bpm-ref').value,
            notes:        document.getElementById('bpm-pay-notes').value,
        };
        if (!payload.amount) { showToast('Amount required', 'error'); return; }
        try {
            const res = await fetch(`/api/billing/subscriptions/${clientId}/confirm-payment`, {
                method: 'POST', credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed');
            showToast(`Payment confirmed ✓  New expiry: ${data.new_period_ends_at}`, 'success');
            closePayModal();
            load();
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    }

    // ════════════════════════════════
    // ADDON HELPERS
    // ════════════════════════════════

    async function addAddon(clientId, addonKey) {
        const period = document.getElementById('bm-period')?.value || 'monthly';
        try {
            const res = await fetch(`/api/billing/subscriptions/${clientId}/addons`, {
                method: 'POST', credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ addon_key: addonKey, period }),
            });
            if (!res.ok) throw new Error(await res.text());
            showToast('Addon added ✓', 'success');
            openModal(clientId);   // re-render modal
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    }

    async function removeAddon(clientId, addonKey) {
        try {
            const res = await fetch(`/api/billing/subscriptions/${clientId}/addons/${addonKey}`, {
                method: 'DELETE', credentials: 'include',
            });
            if (!res.ok) throw new Error(await res.text());
            showToast('Addon removed', 'success');
            openModal(clientId);
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    }

    // ════════════════════════════════
    // CREATE SUBSCRIPTION (onboarding ke liye)
    // ════════════════════════════════

    async function createForRestaurant(clientId) {
        const planOpts = _plans.map(p =>
            `<option value="${p.key}">${p.name} — ₹${p.monthly_price}/mo</option>`
        ).join('');

        // Simple inline modal
        const html = `
        <div id="bm-create-overlay" style="position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;" onclick="if(event.target===this)document.getElementById('bm-create-overlay').remove()">
            <div style="background:#1a1a2e;border:1px solid var(--border);border-radius:14px;padding:24px;width:420px;max-width:95vw;">
                <div style="font-size:1rem;font-weight:700;color:white;margin-bottom:16px;">Subscription — ${clientId}</div>

                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                    <div class="form-group" style="margin:0;">
                        <label>Status</label>
                        <select id="bc-status" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                            <option value="trial">Trial (30 days)</option>
                            <option value="demo">Demo (never expires)</option>
                            <option value="active">Active</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin:0;">
                        <label>Plan</label>
                        <select id="bc-plan" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                            ${planOpts}
                        </select>
                    </div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;">
                    <div class="form-group" style="margin:0;">
                        <label>Period</label>
                        <select id="bc-period" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                            <option value="monthly">Monthly</option>
                            <option value="halfyearly">Half-yearly</option>
                            <option value="yearly">Yearly</option>
                        </select>
                    </div>
                    <div class="form-group" style="margin:0;">
                        <label>Discount %</label>
                        <input type="number" id="bc-dpct" value="0" min="0" max="100"
                            style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                    </div>
                    <div class="form-group" style="margin:0;">
                        <label>Discount ₹</label>
                        <input type="number" id="bc-dflat" value="0" min="0"
                            style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                    </div>
                </div>

                <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:16px;">
                    <button onclick="document.getElementById('bm-create-overlay').remove()"
                        style="padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;">
                        Cancel</button>
                    <button onclick="Billing._submitCreate('${clientId}')"
                        style="padding:8px 20px;border-radius:8px;border:none;background:var(--primary);color:white;font-weight:600;cursor:pointer;">
                        Create</button>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', html);
    }

    async function _submitCreate(clientId) {
        const payload = {
            status:           document.getElementById('bc-status').value,
            plan_key:         document.getElementById('bc-plan').value,
            period:           document.getElementById('bc-period').value,
            discount_percent: parseInt(document.getElementById('bc-dpct').value || 0),
            discount_flat:    parseInt(document.getElementById('bc-dflat').value || 0),
        };
        try {
            const res = await fetch(`/api/billing/subscriptions/${clientId}`, {
                method: 'POST', credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(await res.text());
            document.getElementById('bm-create-overlay')?.remove();
            showToast('Subscription created ✓', 'success');
            load();
        } catch (e) {
            showToast('Error: ' + e.message, 'error');
        }
    }

    // ════════════════════════════════
    // DOM HELPERS
    // ════════════════════════════════

    function _ensureModal() {
        if (document.getElementById('bm-overlay')) return;
        document.body.insertAdjacentHTML('beforeend', `
        <div id="bm-overlay" style="display:none;position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.6);backdrop-filter:blur(3px);align-items:center;justify-content:center;" onclick="if(event.target===this)Billing.closeModal()">
            <div style="background:#1a1a2e;border:1px solid var(--border);border-radius:14px;width:600px;max-width:95vw;max-height:90vh;display:flex;flex-direction:column;">
                <div style="display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--border);">
                    <div id="bm-title" style="font-size:1rem;font-weight:700;color:white;"></div>
                    <button onclick="Billing.closeModal()" style="background:transparent;border:none;color:var(--muted);font-size:1.2rem;cursor:pointer;">✕</button>
                </div>
                <div id="bm-body" style="padding:20px;overflow-y:auto;flex:1;"></div>
                <div style="display:flex;justify-content:flex-end;gap:8px;padding:14px 20px;border-top:1px solid var(--border);">
                    <button onclick="Billing.closeModal()" style="padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;">Cancel</button>
                    <button onclick="Billing.save()" style="padding:8px 20px;border-radius:8px;border:none;background:var(--primary);color:white;font-weight:600;cursor:pointer;">Save Changes</button>
                </div>
            </div>
        </div>`);
    }

    function _ensurePayModal() {
        if (document.getElementById('bpm-overlay')) return;
        document.body.insertAdjacentHTML('beforeend', `
        <div id="bpm-overlay" style="display:none;position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,0.6);backdrop-filter:blur(3px);align-items:center;justify-content:center;" onclick="if(event.target===this)Billing.closePayModal()">
            <div style="background:#1a1a2e;border:1px solid var(--border);border-radius:14px;width:480px;max-width:95vw;max-height:90vh;display:flex;flex-direction:column;">
                <div style="display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--border);">
                    <div style="font-size:1rem;font-weight:700;color:white;">
                        Confirm Payment — <span id="bpm-client-id"></span>
                    </div>
                    <button onclick="Billing.closePayModal()" style="background:transparent;border:none;color:var(--muted);font-size:1.2rem;cursor:pointer;">✕</button>
                </div>
                <div style="padding:20px;overflow-y:auto;flex:1;">
                    <input type="hidden" id="bpm-cid">

                    <!-- QR -->
                    <div style="display:flex;justify-content:center;margin-bottom:16px;">
                        <div id="bpm-qr" style="padding:12px;background:#1a1a2e;border:1px solid var(--border);border-radius:10px;display:inline-block;"></div>
                    </div>
                    <div id="bpm-upi-str" style="font-size:0.68rem;color:var(--muted);word-break:break-all;text-align:center;margin-bottom:16px;font-family:var(--font-m);"></div>

                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div class="form-group" style="margin:0;">
                            <label>Amount (₹)</label>
                            <input type="number" id="bpm-amount" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                        </div>
                        <div class="form-group" style="margin:0;">
                            <label>Period</label>
                            <select id="bpm-period" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                                <option value="monthly">Monthly</option>
                                <option value="halfyearly">Half-yearly</option>
                                <option value="yearly">Yearly</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin:0;">
                            <label>Payment Mode</label>
                            <select id="bpm-mode" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;">
                                <option value="upi">UPI</option>
                                <option value="cash">Cash</option>
                                <option value="bank_transfer">Bank Transfer</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin:0;">
                            <label>Reference ID</label>
                            <input type="text" id="bpm-ref" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;font-family:var(--font-m);font-size:0.8rem;">
                        </div>
                    </div>
                    <div class="form-group" style="margin:0;">
                        <label>Notes</label>
                        <textarea id="bpm-pay-notes" rows="2" style="width:100%;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:white;padding:9px;border-radius:8px;outline:none;resize:none;font-size:0.82rem;" placeholder="Optional..."></textarea>
                    </div>
                </div>
                <div style="display:flex;justify-content:flex-end;gap:8px;padding:14px 20px;border-top:1px solid var(--border);">
                    <button onclick="Billing.closePayModal()" style="padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;">Cancel</button>
                    <button onclick="Billing.submitConfirmPayment()" style="padding:8px 20px;border-radius:8px;border:none;background:#43e97b;color:#0d1117;font-weight:700;cursor:pointer;">✓ Confirm & Extend</button>
                </div>
            </div>
        </div>`);

        // QRCode.js CDN load karo agar nahi hai
        if (!window.QRCode) {
            const s = document.createElement('script');
            s.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js';
            document.head.appendChild(s);
        }
    }

    // ── Public API ──
    return {
        load,
        setFilter,
        openModal,
        closeModal,
        save,
        openConfirmPayment,
        closePayModal,
        submitConfirmPayment,
        addAddon,
        removeAddon,
        createForRestaurant,
        _onStatusChange,
        _refreshPreview,
        _submitCreate,
    };

})();

// ════════════════════════════════
// PLANS & ADD-ONS EDITOR
// ════════════════════════════════
const PlansEditor = (() => {

    let _plans = [];
    let _addons = [];
    let _isShowingPlans = false;

    function toggleSubTab() {
        const toggleBtn = document.getElementById('btn-billing-toggle');
        const mainTitle = document.getElementById('billing-main-title');
        const subsView  = document.getElementById('billing-subscriptions-view');
        const plansView = document.getElementById('billing-plans-view');

        _isShowingPlans = !_isShowingPlans;

        if (_isShowingPlans) {
            subsView.style.display  = 'none';
            plansView.style.display = 'block';
            toggleBtn.innerHTML     = '📋 View Subscriptions';
            mainTitle.textContent   = '🏷️ Manage Plans & Add-ons';
            load();
        } else {
            subsView.style.display  = 'block';
            plansView.style.display = 'none';
            toggleBtn.innerHTML     = '🏷️ Manage Plans & Add-ons';
            mainTitle.textContent   = '💳 Billing & Subscriptions';
            Billing.load();
        }
    }

    async function load() {
        const plansGrid  = document.getElementById('plans-editor-grid');
        const addonsGrid = document.getElementById('addons-editor-grid');
        plansGrid.innerHTML  = '<div class="loading">Loading Plans...</div>';
        addonsGrid.innerHTML = '<div class="loading">Loading Add-ons...</div>';

        try {
            // Fetch plans and addons
            const [plansRes, addonsRes] = await Promise.all([
                fetch('/api/billing/plans', { credentials: 'include' }),
                fetch('/api/billing/addons', { credentials: 'include' })
            ]);

            _plans  = await plansRes.json();
            _addons = await addonsRes.json();

            render();
        } catch (e) {
            plansGrid.innerHTML  = `<div class="empty">Error: ${e.message}</div>`;
            addonsGrid.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function render() {
        const plansGrid  = document.getElementById('plans-editor-grid');
        const addonsGrid = document.getElementById('addons-editor-grid');

        // Extract all unique feature keys and labels for dynamic checklist
        const allFeatureKeys = new Set();
        const featureLabelsMap = {};
        _plans.forEach(p => {
            if (p.features && p.features.included) {
                p.features.included.forEach(f => allFeatureKeys.add(f));
            }
            if (p.features && p.features.labels) {
                Object.entries(p.features.labels).forEach(([fk, lbl]) => {
                    allFeatureKeys.add(fk);
                    featureLabelsMap[fk] = lbl;
                });
            }
        });

        // Render Plans
        plansGrid.innerHTML = _plans.map(p => {
            const key = p.key;
            return `
            <div class="card" style="border: 1px solid var(--border); background: var(--surface); display: flex; flex-direction: column; margin-bottom: 0;">
                <div class="card-head" style="padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-family: var(--font-m); font-size: 0.65rem; background: rgba(108,99,255,0.12); color: var(--primary); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(108,99,255,0.2);">${key.toUpperCase()}</span>
                        <span style="font-family: var(--font-d); font-weight: 700; font-size: 1rem; color: white;">Plan config</span>
                    </div>
                    <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.72rem; color: var(--muted); margin: 0; text-transform: none; letter-spacing: 0;">
                        <input type="checkbox" id="plan-active-${key}" ${p.is_active ? 'checked' : ''} style="cursor: pointer; width: 14px; height: 14px; accent-color: var(--primary);"> Active
                    </label>
                </div>
                
                <div class="card-body" style="padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; flex: 1;">
                    <div class="form-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div class="form-group" style="margin: 0;">
                            <label>Plan Name</label>
                            <input type="text" id="plan-name-${key}" value="${p.name.replace(/"/g, '&quot;')}" placeholder="Name">
                        </div>
                        <div class="form-group" style="margin: 0;">
                            <label>Monthly Price (₹)</label>
                            <input type="number" id="plan-price-${key}" value="${p.monthly_price}" min="0">
                        </div>
                    </div>

                    <div class="form-grid" style="display: grid; grid-template-columns: 1.5fr 0.5fr; gap: 10px;">
                        <div class="form-group" style="margin: 0;">
                            <label>Tagline</label>
                            <input type="text" id="plan-tagline-${key}" value="${(p.tagline || '').replace(/"/g, '&quot;')}" placeholder="Tagline description">
                        </div>
                        <div class="form-group" style="margin: 0;">
                            <label>Sort Order</label>
                            <input type="number" id="plan-sort-${key}" value="${p.sort_order || 0}" min="0">
                        </div>
                    </div>

                    <!-- Features checklist -->
                    <div style="margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; display: flex; flex-direction: column; gap: 8px;">
                        <label style="font-family: var(--font-m); font-size: 0.62rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 2px;">Included Features & Descriptive Labels</label>
                        
                        <div style="display: flex; flex-direction: column; gap: 8px; max-height: 200px; overflow-y: auto; padding-right: 4px; border: 1px solid rgba(255,255,255,0.04); border-radius: 8px; padding: 10px; background: rgba(0,0,0,0.2);" class="custom-scroll">
                            ${Array.from(allFeatureKeys).map(fkey => {
                                const isIncluded = p.features && p.features.included && p.features.included.includes(fkey);
                                const currentLabel = (p.features && p.features.labels && p.features.labels[fkey]) || featureLabelsMap[fkey] || fkey;
                                return `
                                <div style="display: flex; align-items: flex-start; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.02); padding-bottom: 6px; margin-bottom: 4px;">
                                    <input type="checkbox" data-feature-key="${fkey}" class="plan-feature-chk-${key}" ${isIncluded ? 'checked' : ''} style="margin-top: 4px; cursor: pointer; width: 14px; height: 14px; accent-color: var(--primary); flex-shrink: 0;">
                                    <div style="flex: 1; min-width: 0;">
                                        <div style="font-size: 0.72rem; color: white; font-family: var(--font-m); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${fkey}</div>
                                        <input type="text" data-feature-label-key="${fkey}" class="plan-feature-label-input-${key}" value="${currentLabel.replace(/"/g, '&quot;')}" style="font-size: 0.68rem; padding: 4px 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); color: var(--text); border-radius: 4px; width: 100%; margin-top: 3px;" placeholder="Visual description label...">
                                    </div>
                                </div>`;
                            }).join('')}
                        </div>
                    </div>

                    <button class="btn btn-primary" onclick="PlansEditor.savePlan('${key}', this)" style="width: 100%; margin-top: auto; padding: 10px; display: flex; align-items: center; justify-content: center; gap: 8px; font-weight: 600; height: 38px;">
                        💾 Save Plan Config
                    </button>
                </div>
            </div>
            `;
        }).join('');

        // Render Addons
        addonsGrid.innerHTML = _addons.map(a => {
            const key = a.key;
            return `
            <div class="card" style="border: 1px solid var(--border); background: var(--surface); display: flex; flex-direction: column; margin-bottom: 0;">
                <div class="card-head" style="padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-family: var(--font-m); font-size: 0.65rem; background: rgba(108,99,255,0.12); color: var(--primary); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(108,99,255,0.2);">${key.toUpperCase()}</span>
                        <span style="font-family: var(--font-d); font-weight: 700; font-size: 1rem; color: white;">Add-on config</span>
                    </div>
                    <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.72rem; color: var(--muted); margin: 0; text-transform: none; letter-spacing: 0;">
                        <input type="checkbox" id="addon-active-${key}" ${a.is_active ? 'checked' : ''} style="cursor: pointer; width: 14px; height: 14px; accent-color: var(--primary);"> Active
                    </label>
                </div>

                <div class="card-body" style="padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; flex: 1;">
                    <div class="form-group" style="margin: 0;">
                        <label>Add-on Name</label>
                        <input type="text" id="addon-name-${key}" value="${a.name.replace(/"/g, '&quot;')}" placeholder="Name">
                    </div>

                    <div class="form-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div class="form-group" style="margin: 0;">
                            <label>Monthly Price (₹)</label>
                            <input type="number" id="addon-price-${key}" value="${a.monthly_price || 0}" min="0">
                        </div>
                        <div class="form-group" style="margin: 0;">
                            <label>One-time Price (₹)</label>
                            <input type="number" id="addon-otprice-${key}" value="${a.one_time_price || 0}" min="0">
                        </div>
                    </div>

                    <div style="display: flex; align-items: center; gap: 6px; padding: 2px 0;">
                        <input type="checkbox" id="addon-one-time-${key}" ${a.one_time_only ? 'checked' : ''} style="cursor: pointer; width: 14px; height: 14px;" disabled>
                        <label style="font-size: 0.72rem; color: var(--muted); cursor: not-allowed; margin: 0; text-transform: none; letter-spacing: 0;">
                            One-time only purchase (Type locked)
                        </label>
                    </div>

                    <div class="form-group" style="margin: 0;">
                        <label>Description</label>
                        <textarea id="addon-desc-${key}" rows="3" placeholder="Description of the add-on features..." style="resize: vertical; min-height: 80px;">${a.description || ''}</textarea>
                    </div>

                    <button class="btn btn-primary" onclick="PlansEditor.saveAddon('${key}', this)" style="width: 100%; margin-top: auto; padding: 10px; display: flex; align-items: center; justify-content: center; gap: 8px; font-weight: 600; height: 38px;">
                        💾 Save Add-on Config
                    </button>
                </div>
            </div>
            `;
        }).join('');
    }

    async function savePlan(key, btn) {
        const origHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = 'Saving...';

        try {
            const included = [];
            const labels = {};

            // 1. Gather all checkbox statuses
            document.querySelectorAll(`.plan-feature-chk-${key}:checked`).forEach(chk => {
                included.push(chk.getAttribute('data-feature-key'));
            });

            // 2. Gather all input labels
            document.querySelectorAll(`.plan-feature-label-input-${key}`).forEach(inp => {
                const fk  = inp.getAttribute('data-feature-label-key');
                const val = inp.value.trim();
                if (val) labels[fk] = val;
            });

            // 3. Form payload
            const payload = {
                name:          document.getElementById(`plan-name-${key}`).value.trim(),
                monthly_price: parseInt(document.getElementById(`plan-price-${key}`).value) || 0,
                tagline:       document.getElementById(`plan-tagline-${key}`).value.trim(),
                sort_order:    parseInt(document.getElementById(`plan-sort-${key}`).value) || 0,
                is_active:     document.getElementById(`plan-active-${key}`).checked,
                features:      { included, labels }
            };

            if (!payload.name) { showToast('Plan name is required', 'error'); btn.disabled = false; btn.innerHTML = origHtml; return; }

            // 4. Send PATCH
            const res = await fetch(`/api/billing/plans/${key}`, {
                method: 'PATCH',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error(await res.text());

            showToast(`Plan '${key}' updated successfully! ✓`, 'success');
            load(); // Re-fetch to sync
        } catch (e) {
            showToast('Save failed: ' + e.message, 'error');
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }

    async function saveAddon(key, btn) {
        const origHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = 'Saving...';

        try {
            const payload = {
                name:          document.getElementById(`addon-name-${key}`).value.trim(),
                monthly_price: parseInt(document.getElementById(`addon-price-${key}`).value) || 0,
                one_time_price: parseInt(document.getElementById(`addon-otprice-${key}`).value) || 0,
                description:   document.getElementById(`addon-desc-${key}`).value.trim(),
                is_active:     document.getElementById(`addon-active-${key}`).checked
            };

            if (!payload.name) { showToast('Add-on name is required', 'error'); btn.disabled = false; btn.innerHTML = origHtml; return; }

            // Send PATCH
            const res = await fetch(`/api/billing/addons/${key}`, {
                method: 'PATCH',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error(await res.text());

            showToast(`Add-on '${key}' updated successfully! ✓`, 'success');
            load(); // Re-fetch to sync
        } catch (e) {
            showToast('Save failed: ' + e.message, 'error');
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    }

    return {
        toggleSubTab,
        load,
        savePlan,
        saveAddon
    };

})();

// ── Global helpers ──
function showToast(msg, type = '') {
    if (typeof toast === 'function') {
        toast(msg, type);
    } else if (typeof window.toast === 'function') {
        window.toast(msg, type);
    } else {
        alert(msg);
    }
}

// ── Global helpers for HTML onclick ──
function loadBilling()              { Billing.load(); }
function setBillingFilter(f, el)    { Billing.setFilter(f, el); }
function toggleBillingSubTab()      { PlansEditor.toggleSubTab(); }
