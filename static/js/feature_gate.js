/**
 * feature_gate.js — FE Feature Locking Utility
 * Kisi bhi template mein include karo aur use karo.
 */

const FeatureGate = (() => {
    let _features = null;  // session cache

    async function load() {
        if (_features) return _features;
        try {
            const res  = await fetch('/api/billing/features/me', { credentials: 'include' });
            const data = await res.json();
            _features  = data.features || {};
        } catch (e) {
            _features = {};
            console.warn('FeatureGate: load failed', e);
        }
        return _features;
    }

    async function has(featureKey) {
        const f = await load();
        return !!f[featureKey];
    }

    /**
     * Kisi section/div ko gate karo — lock overlay lagao
     * @param featureKey  "owner_analytics", "ar_menu", etc.
     * @param elementId   DOM element id jisko gate karna hai
     * @param upgradeMsg  Optional custom message
     */
    async function gate(featureKey, elementId, upgradeMsg) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const allowed = await has(featureKey);
        if (!allowed) {
            el.style.position      = 'relative';
            el.style.pointerEvents = 'none';
            el.style.opacity       = '0.45';

            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position:absolute; inset:0;
                display:flex; flex-direction:column;
                align-items:center; justify-content:center;
                background:rgba(0,0,0,0.55);
                border-radius:inherit; z-index:10;
                pointer-events:auto;
            `;
            overlay.innerHTML = `
                <div style="font-size:1.5rem;">🔒</div>
                <div style="color:white;font-size:0.85rem;margin-top:6px;
                            text-align:center;padding:0 16px;max-width:220px;">
                    ${upgradeMsg || 'Yeh feature aapke plan mein nahi hai'}
                </div>
                <button onclick="window.location.href='/pricing'"
                    style="margin-top:10px;padding:6px 18px;border-radius:6px;
                           background:#6c63ff;color:white;border:none;
                           cursor:pointer;font-size:0.8rem;">
                    Upgrade Karein →
                </button>
            `;
            el.appendChild(overlay);
        }
    }

    /**
     * Button/link ko gate karo — click pe message dikhao
     */
    async function gateButton(featureKey, buttonId, upgradeMsg) {
        const allowed = await has(featureKey);
        if (!allowed) {
            const btn = document.getElementById(buttonId);
            if (!btn) return;
            btn.disabled      = true;
            btn.title         = upgradeMsg || 'Plan upgrade required';
            btn.style.opacity = '0.5';
            btn.style.cursor  = 'not-allowed';
            btn.onclick = (e) => {
                e.preventDefault();
                alert(upgradeMsg || 'Yeh feature aapke plan mein nahi hai. Upgrade karein.');
            };
        }
    }

    return { load, has, gate, gateButton };
})();
