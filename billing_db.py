"""
billing_db.py — ZenTable subscription billing
Same Neon DB, same connection pool as database.py

Tables:
  billing_plans        — Basic / Pro / Elite config
  billing_addons       — AR Menu / Kitchen Tab / Attendance
  subscriptions        — per-restaurant subscription state
  subscription_addons  — per-restaurant active add-ons
  payment_history      — every payment record
  email_log            — expiry email deduplication
"""

from database import _pool, _PgConn          # same pool, no extra connections
import json
from datetime import datetime, date, timedelta


def get_db() -> _PgConn:
    return _PgConn()


# ════════════════════════════════
# INIT — create tables + seed default plans/addons
# ════════════════════════════════

def init_billing_tables():
    conn = get_db()
    cur  = conn._conn.cursor()

    # ── billing_plans ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS billing_plans (
            id            SERIAL PRIMARY KEY,
            key           TEXT UNIQUE NOT NULL,
            name          TEXT NOT NULL,
            tagline       TEXT,
            monthly_price INT  NOT NULL DEFAULT 0,
            features      JSONB NOT NULL DEFAULT '{"included": [], "labels": {}}',
            is_active     BOOLEAN DEFAULT true,
            sort_order    INT DEFAULT 0,
            created_at    TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── billing_addons ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS billing_addons (
            id            SERIAL PRIMARY KEY,
            key           TEXT UNIQUE NOT NULL,
            name          TEXT NOT NULL,
            description   TEXT,
            monthly_price INT  NOT NULL DEFAULT 0,
            one_time_only BOOLEAN DEFAULT false,
            one_time_price INT DEFAULT 0,
            is_active     BOOLEAN DEFAULT true,
            created_at    TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── subscriptions ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            client_id                TEXT PRIMARY KEY,
            status                   TEXT NOT NULL DEFAULT 'trial',
            plan_key                 TEXT REFERENCES billing_plans(key),
            period                   TEXT DEFAULT 'monthly',
            base_price               INT  DEFAULT 0,
            discount_percent         INT  DEFAULT 0,
            discount_flat            INT  DEFAULT 0,
            final_price              INT  DEFAULT 0,
            trial_ends_at            TEXT,
            current_period_ends_at   TEXT,
            grace_ends_at            TEXT,
            admin_notes              TEXT,
            razorpay_plan_id         TEXT,
            razorpay_subscription_id TEXT,
            razorpay_customer_id     TEXT,
            payment_method           TEXT DEFAULT 'manual',
            created_at               TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            updated_at               TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── subscription_addons ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscription_addons (
            id               SERIAL PRIMARY KEY,
            client_id        TEXT NOT NULL,
            addon_key        TEXT REFERENCES billing_addons(key),
            period           TEXT NOT NULL DEFAULT 'monthly',
            base_price       INT  DEFAULT 0,
            discount_percent INT  DEFAULT 0,
            discount_flat    INT  DEFAULT 0,
            final_price      INT  DEFAULT 0,
            starts_at        TEXT,
            ends_at          TEXT,
            is_active        BOOLEAN DEFAULT true,
            created_at       TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            UNIQUE(client_id, addon_key)
        )
    """)

    # ── payment_history ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_history (
            id                  SERIAL PRIMARY KEY,
            client_id           TEXT NOT NULL,
            amount              INT  NOT NULL,
            period              TEXT,
            payment_type        TEXT DEFAULT 'subscription',
            reference_id        TEXT,
            payment_mode        TEXT DEFAULT 'upi',
            status              TEXT DEFAULT 'pending',
            confirmed_by        TEXT,
            confirmed_at        TEXT,
            notes               TEXT,
            razorpay_payment_id TEXT,
            created_at          TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ── email_log ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            id          SERIAL PRIMARY KEY,
            client_id   TEXT NOT NULL,
            email_type  TEXT NOT NULL,
            sent_at     TEXT NOT NULL,
            status      TEXT DEFAULT 'sent',
            UNIQUE(client_id, email_type, sent_at)
        )
    """)

    # ── Seed default plans (ON CONFLICT = update prices/features if changed) ──
    default_plans = [
        {
            "key":           "basic",
            "name":          "Basic",
            "tagline":       "Single outlet, shuruwaat",
            "monthly_price": 1499,
            "sort_order":    1,
            "features": {
                "included": [
                    "website", "qr_ordering", "digital_menu",
                    "staff_panel", "basic_pos", "ai_menu_import", "blog"
                ],
                "labels": {
                    "website":        "Personal website (zentable.in/restaurant)",
                    "qr_ordering":    "QR Ordering + Digital Menu",
                    "digital_menu":   "Digital Menu",
                    "staff_panel":    "Staff Panel (Waiter, Kitchen, Counter)",
                    "basic_pos":      "Basic POS",
                    "ai_menu_import": "Photo to Menu (AI)",
                    "blog":           "Personal Blog Page",
                }
            }
        },
        {
            "key":           "pro",
            "name":          "Pro",
            "tagline":       "Mid-size, growth-focused",
            "monthly_price": 2999,
            "sort_order":    2,
            "features": {
                "included": [
                    "website", "qr_ordering", "digital_menu",
                    "staff_panel", "basic_pos", "ai_menu_import", "blog",
                    "owner_analytics", "ai_chatbot", "multi_branch"
                ],
                "labels": {
                    "website":          "Personal website (zentable.in/restaurant)",
                    "qr_ordering":      "QR Ordering + Digital Menu",
                    "digital_menu":     "Digital Menu",
                    "staff_panel":      "Staff Panel (Waiter, Kitchen, Counter)",
                    "basic_pos":        "Basic POS",
                    "ai_menu_import":   "Photo to Menu (AI)",
                    "blog":             "Personal Blog Page",
                    "owner_analytics":  "Owner Analytics Dashboard",
                    "ai_chatbot":       "AI Chat Support (Analytics)",
                    "multi_branch":     "Multi-branch / Outlets",
                }
            }
        },
        {
            "key":           "elite",
            "name":          "Elite",
            "tagline":       "Chains, multi-outlet",
            "monthly_price": 5499,
            "sort_order":    3,
            "features": {
                "included": [
                    "website", "qr_ordering", "digital_menu",
                    "staff_panel", "basic_pos", "ai_menu_import", "blog",
                    "owner_analytics", "ai_chatbot", "multi_branch",
                    "centralized_reporting", "custom_integrations", "dedicated_support"
                ],
                "labels": {
                    "website":                "Personal website (zentable.in/restaurant)",
                    "qr_ordering":            "QR Ordering + Digital Menu",
                    "digital_menu":           "Digital Menu",
                    "staff_panel":            "Staff Panel (Waiter, Kitchen, Counter)",
                    "basic_pos":              "Basic POS",
                    "ai_menu_import":         "Photo to Menu (AI)",
                    "blog":                   "Personal Blog Page",
                    "owner_analytics":        "Owner Analytics Dashboard",
                    "ai_chatbot":             "AI Chat Support (Analytics)",
                    "multi_branch":           "Multi-branch / Outlets",
                    "centralized_reporting":  "Centralized Reporting",
                    "custom_integrations":    "Custom Integrations",
                    "dedicated_support":      "Dedicated Account Manager",
                }
            }
        },
    ]

    for p in default_plans:
        cur.execute("""
            INSERT INTO billing_plans (key, name, tagline, monthly_price, features, sort_order)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (key) DO NOTHING
        """, (
            p["key"], p["name"], p["tagline"],
            p["monthly_price"],
            json.dumps(p["features"]),
            p["sort_order"]
        ))

    # ── Seed default addons ──
    default_addons = [
        {
            "key":           "ar_menu",
            "name":          "AR Menu",
            "description":   "3D dish preview — customer order karne se pehle dish dekh sakta hai",
            "monthly_price": 799,
            "one_time_only": False,
            "one_time_price": 2000,
        },
        {
            "key":            "kitchen_tab",
            "name":           "Kitchen Tab",
            "description":    "One-screen kitchen panel — orders seedha display pe, no paper slips",
            "monthly_price":  0,
            "one_time_only":  True,
            "one_time_price": 1500,
        },
        {
            "key":            "attendance",
            "name":           "Staff Attendance",
            "description":    "Tab-based attendance + shift management",
            "monthly_price":  399,
            "one_time_only":  False,
            "one_time_price": 1500,
        },
    ]

    for a in default_addons:
        cur.execute("""
            INSERT INTO billing_addons
                (key, name, description, monthly_price, one_time_only, one_time_price)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO NOTHING
        """, (
            a["key"], a["name"], a["description"],
            a["monthly_price"], a["one_time_only"], a["one_time_price"]
        ))

    conn.commit()
    conn.close()
    print("✅ Billing tables initialized")


# ════════════════════════════════
# PLANS
# ════════════════════════════════

def get_all_plans() -> list:
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM billing_plans ORDER BY sort_order"
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_plan(key: str) -> dict | None:
    conn = get_db()
    cur  = conn.execute("SELECT * FROM billing_plans WHERE key=%s", (key,))
    row  = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_plan(key: str, fields: dict):
    """
    Admin se plan update — name, tagline, monthly_price, features, is_active.
    fields = sirf jo change karna ho.
    """
    allowed = {"name", "tagline", "monthly_price", "features", "is_active", "sort_order"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "features":
            sets.append(f"{k} = %s::jsonb")
            vals.append(json.dumps(v))
        else:
            sets.append(f"{k} = %s")
            vals.append(v)
    if not sets:
        return
    vals.append(key)
    conn = get_db()
    conn.execute(
        f"UPDATE billing_plans SET {', '.join(sets)} WHERE key=%s", vals
    )
    conn.commit()
    conn.close()


# ════════════════════════════════
# ADDONS
# ════════════════════════════════

def get_all_addons() -> list:
    conn = get_db()
    cur  = conn.execute("SELECT * FROM billing_addons ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_addon(key: str) -> dict | None:
    conn = get_db()
    cur  = conn.execute("SELECT * FROM billing_addons WHERE key=%s", (key,))
    row  = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_addon(key: str, fields: dict):
    allowed = {"name", "description", "monthly_price", "one_time_price", "is_active"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = %s")
        vals.append(v)
    if not sets:
        return
    vals.append(key)
    conn = get_db()
    conn.execute(
        f"UPDATE billing_addons SET {', '.join(sets)} WHERE key=%s", vals
    )
    conn.commit()
    conn.close()


# ════════════════════════════════
# PRICE CALCULATOR
# ════════════════════════════════

PERIOD_MULTIPLIER = {
    "monthly":    1,
    "halfyearly": 5,
    "yearly":     10,
}

def calc_price(monthly_price: int, period: str,
               discount_percent: int = 0, discount_flat: int = 0) -> dict:
    """
    Final price calculate karo.
    Returns: {base_price, discount_percent, discount_flat, final_price}
    """
    multiplier = PERIOD_MULTIPLIER.get(period, 1)
    base       = monthly_price * multiplier
    after_flat = max(0, base - discount_flat)
    after_pct  = max(0, round(after_flat * (1 - discount_percent / 100)))
    return {
        "base_price":       base,
        "discount_percent": discount_percent,
        "discount_flat":    discount_flat,
        "final_price":      after_pct,
    }


# ════════════════════════════════
# SUBSCRIPTIONS
# ════════════════════════════════

def get_subscription(client_id: str) -> dict | None:
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM subscriptions WHERE client_id=%s", (client_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_subscriptions() -> list:
    """Admin panel ke liye — saari subscriptions"""
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM subscriptions ORDER BY updated_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_subscription(
    client_id:        str,
    status:           str,           # demo | trial | active
    plan_key:         str  = "basic",
    period:           str  = "monthly",
    discount_percent: int  = 0,
    discount_flat:    int  = 0,
    months:           int  = 1,      # active ke liye X months
    admin_notes:      str  = None,
) -> dict:
    """
    Naya subscription create karo — restaurant onboarding pe call hoga.
    status ke hisaab se dates set hongi automatically.
    """
    now     = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    trial_ends_at          = None
    current_period_ends_at = None
    grace_ends_at          = None

    if status == "demo":
        trial_ends_at = "9999-12-31"

    elif status == "trial":
        trial_ends_at = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    elif status == "active":
        plan          = get_plan(plan_key)
        monthly_price = plan["monthly_price"] if plan else 0
        prices        = calc_price(monthly_price, period, discount_percent, discount_flat)
        period_days   = {"monthly": 30, "halfyearly": 180, "yearly": 365}
        days          = period_days.get(period, 30) * months
        end           = now + timedelta(days=days)
        current_period_ends_at = end.strftime("%Y-%m-%d")
        grace_ends_at          = (end + timedelta(days=1)).strftime("%Y-%m-%d")

    plan          = get_plan(plan_key)
    monthly_price = plan["monthly_price"] if plan else 0
    prices        = calc_price(monthly_price, period, discount_percent, discount_flat)

    conn = get_db()
    conn.execute("""
        INSERT INTO subscriptions
            (client_id, status, plan_key, period,
             base_price, discount_percent, discount_flat, final_price,
             trial_ends_at, current_period_ends_at, grace_ends_at,
             admin_notes, created_at, updated_at)
        VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s)
        ON CONFLICT (client_id) DO UPDATE SET
            status                 = EXCLUDED.status,
            plan_key               = EXCLUDED.plan_key,
            period                 = EXCLUDED.period,
            base_price             = EXCLUDED.base_price,
            discount_percent       = EXCLUDED.discount_percent,
            discount_flat          = EXCLUDED.discount_flat,
            final_price            = EXCLUDED.final_price,
            trial_ends_at          = EXCLUDED.trial_ends_at,
            current_period_ends_at = EXCLUDED.current_period_ends_at,
            grace_ends_at          = EXCLUDED.grace_ends_at,
            admin_notes            = EXCLUDED.admin_notes,
            updated_at             = EXCLUDED.updated_at
    """, (
        client_id, status, plan_key, period,
        prices["base_price"], discount_percent, discount_flat, prices["final_price"],
        trial_ends_at, current_period_ends_at, grace_ends_at,
        admin_notes, now_str, now_str
    ))
    conn.commit()
    conn.close()
    return get_subscription(client_id)

def update_subscription(client_id: str, fields: dict):
    """
    Admin se partial update — plan change, discount change, notes, etc.
    Prices automatically recalculate hongi agar plan/period/discount change ho.
    """
    sub = get_subscription(client_id)
    if not sub:
        return None

    allowed = {
        "status", "plan_key", "period",
        "discount_percent", "discount_flat",
        "trial_ends_at", "current_period_ends_at", "grace_ends_at",
        "admin_notes", "payment_method"
    }

    merged = {k: fields.get(k, sub[k]) for k in allowed if k in sub or k in fields}

    # Recalculate price
    plan          = get_plan(merged.get("plan_key", sub["plan_key"]))
    monthly_price = plan["monthly_price"] if plan else 0
    prices        = calc_price(
        monthly_price,
        merged.get("period",           sub["period"]),
        merged.get("discount_percent", sub["discount_percent"]),
        merged.get("discount_flat",    sub["discount_flat"]),
    )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE subscriptions SET
            status                 = %s,
            plan_key               = %s,
            period                 = %s,
            base_price             = %s,
            discount_percent       = %s,
            discount_flat          = %s,
            final_price            = %s,
            trial_ends_at          = %s,
            current_period_ends_at = %s,
            grace_ends_at          = %s,
            admin_notes            = %s,
            payment_method         = %s,
            updated_at             = %s
        WHERE client_id = %s
    """, (
        merged.get("status",                 sub["status"]),
        merged.get("plan_key",               sub["plan_key"]),
        merged.get("period",                 sub["period"]),
        prices["base_price"],
        prices["discount_percent"],
        prices["discount_flat"],
        prices["final_price"],
        merged.get("trial_ends_at",          sub["trial_ends_at"]),
        merged.get("current_period_ends_at", sub["current_period_ends_at"]),
        merged.get("grace_ends_at",          sub["grace_ends_at"]),
        merged.get("admin_notes",            sub["admin_notes"]),
        merged.get("payment_method",         sub.get("payment_method", "manual")),
        now_str,
        client_id
    ))
    conn.commit()
    conn.close()
    return get_subscription(client_id)


# ════════════════════════════════
# CONFIRM PAYMENT — reusable Phase 1 → Phase 3
# ════════════════════════════════

def confirm_payment(
    client_id:    str,
    amount:       int,
    period:       str,
    payment_mode: str  = "upi",
    reference_id: str  = None,
    confirmed_by: str  = "admin",       # Phase 3 mein "razorpay_webhook" aayega
    notes:        str  = None,
    razorpay_payment_id: str = None,
) -> dict:
    """
    Payment confirm karo — subscription extend karo.
    Phase 1: confirmed_by = admin username
    Phase 3: confirmed_by = "razorpay_webhook", razorpay_payment_id filled
    """
    now     = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Payment history mein add karo
    conn = get_db()
    cur  = conn._conn.cursor()
    cur.execute("""
        INSERT INTO payment_history
            (client_id, amount, period, payment_mode,
             reference_id, status, confirmed_by, confirmed_at,
             notes, razorpay_payment_id)
        VALUES (%s,%s,%s,%s, %s,'confirmed',%s,%s, %s,%s)
        RETURNING id
    """, (
        client_id, amount, period, payment_mode,
        reference_id, confirmed_by, now_str,
        notes, razorpay_payment_id
    ))
    payment_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    # Subscription extend karo
    sub = get_subscription(client_id)
    if not sub:
        return {"payment_id": payment_id, "error": "Subscription not found"}

    period_days = {"monthly": 30, "halfyearly": 180, "yearly": 365}
    days        = period_days.get(period, 30)

    # max(today, current_period_ends_at) — early renewal protected
    if sub["current_period_ends_at"]:
        try:
            existing_end = datetime.strptime(sub["current_period_ends_at"], "%Y-%m-%d")
            start_from   = max(now, existing_end)
        except Exception:
            start_from = now
    else:
        start_from = now

    new_end   = start_from + timedelta(days=days)
    new_grace = new_end + timedelta(days=1)

    update_subscription(client_id, {
        "status":                 "active",
        "current_period_ends_at": new_end.strftime("%Y-%m-%d"),
        "grace_ends_at":          new_grace.strftime("%Y-%m-%d"),
    })

    return {
        "payment_id":  payment_id,
        "client_id":   client_id,
        "new_period_ends_at": new_end.strftime("%Y-%m-%d"),
    }


# ════════════════════════════════
# SUBSCRIPTION ADDONS
# ════════════════════════════════

def get_subscription_addons(client_id: str) -> list:
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM subscription_addons WHERE client_id=%s ORDER BY addon_key",
        (client_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def upsert_subscription_addon(
    client_id:        str,
    addon_key:        str,
    period:           str  = "monthly",
    discount_percent: int  = 0,
    discount_flat:    int  = 0,
    ends_at:          str  = None,
) -> dict:
    """Add or update a restaurant's addon."""
    addon         = get_addon(addon_key)
    monthly_price = addon["monthly_price"] if addon else 0
    prices        = calc_price(monthly_price, period, discount_percent, discount_flat)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute("""
        INSERT INTO subscription_addons
            (client_id, addon_key, period,
             base_price, discount_percent, discount_flat, final_price,
             starts_at, ends_at, is_active)
        VALUES (%s,%s,%s, %s,%s,%s,%s, %s,%s, true)
        ON CONFLICT (client_id, addon_key) DO UPDATE SET
            period           = EXCLUDED.period,
            base_price       = EXCLUDED.base_price,
            discount_percent = EXCLUDED.discount_percent,
            discount_flat    = EXCLUDED.discount_flat,
            final_price      = EXCLUDED.final_price,
            ends_at          = EXCLUDED.ends_at,
            is_active        = true
    """, (
        client_id, addon_key, period,
        prices["base_price"], discount_percent, discount_flat, prices["final_price"],
        now_str, ends_at
    ))
    conn.commit()
    conn.close()
    return prices

def remove_subscription_addon(client_id: str, addon_key: str):
    conn = get_db()
    conn.execute(
        "UPDATE subscription_addons SET is_active=false WHERE client_id=%s AND addon_key=%s",
        (client_id, addon_key)
    )
    conn.commit()
    conn.close()


# ════════════════════════════════
# PAYMENT HISTORY
# ════════════════════════════════

def get_payment_history(client_id: str) -> list:
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM payment_history WHERE client_id=%s ORDER BY created_at DESC",
        (client_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def generate_reference_id(client_id: str) -> str:
    """ZT-SPICEGARDEN-JUN26 format"""
    month = datetime.now().strftime("%b%y").upper()
    cid   = client_id.upper().replace("_", "")[:12]
    return f"ZT-{cid}-{month}"


# ════════════════════════════════
# CRON — daily status check + email triggers
# ════════════════════════════════

def run_daily_billing_cron(send_email_fn=None):
    """
    Roz chalega — FastAPI lifespan background task se.
    1. Trial expire → grace
    2. Period expire → grace
    3. Grace expire → expired
    4. Email triggers — 7day, 1day, grace, expired
    send_email_fn(client_id, email_type) — caller provide karega
    """
    now       = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    now_str   = now.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    cur  = conn._conn.cursor()

    # Trial expire → grace (1 day)
    cur.execute("""
        UPDATE subscriptions
        SET status        = 'grace',
            grace_ends_at = TO_CHAR(NOW() + INTERVAL '1 day', 'YYYY-MM-DD'),
            updated_at    = %s
        WHERE status = 'trial'
          AND trial_ends_at IS NOT NULL
          AND trial_ends_at != '9999-12-31'
          AND trial_ends_at < %s
    """, (now_str, today_str))

    # Period expire → grace
    cur.execute("""
        UPDATE subscriptions
        SET status        = 'grace',
            grace_ends_at = TO_CHAR(NOW() + INTERVAL '1 day', 'YYYY-MM-DD'),
            updated_at    = %s
        WHERE status = 'active'
          AND current_period_ends_at IS NOT NULL
          AND current_period_ends_at < %s
    """, (now_str, today_str))

    # Grace expire → expired
    cur.execute("""
        UPDATE subscriptions
        SET status     = 'expired',
            updated_at = %s
        WHERE status = 'grace'
          AND grace_ends_at IS NOT NULL
          AND grace_ends_at < %s
    """, (now_str, today_str))

    conn.commit()

    # Email triggers
    if send_email_fn:
        # 7 days pehle
        day7 = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        cur.execute("""
            SELECT client_id FROM subscriptions
            WHERE status IN ('trial','active')
              AND (
                (trial_ends_at = %s AND trial_ends_at != '9999-12-31')
                OR current_period_ends_at = %s
              )
        """, (day7, day7))
        for row in cur.fetchall():
            _send_once(conn, row[0], "expiry_7day", today_str, send_email_fn)

        # 1 day pehle
        day1 = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        cur.execute("""
            SELECT client_id FROM subscriptions
            WHERE status IN ('trial','active')
              AND (
                (trial_ends_at = %s AND trial_ends_at != '9999-12-31')
                OR current_period_ends_at = %s
              )
        """, (day1, day1))
        for row in cur.fetchall():
            _send_once(conn, row[0], "expiry_1day", today_str, send_email_fn)

        # Grace mein hain aaj
        cur.execute("""
            SELECT client_id FROM subscriptions WHERE status = 'grace'
        """)
        for row in cur.fetchall():
            _send_once(conn, row[0], "grace", today_str, send_email_fn)

        # Aaj expire hue
        cur.execute("""
            SELECT client_id FROM subscriptions
            WHERE status = 'expired'
              AND updated_at >= %s
        """, (today_str,))
        for row in cur.fetchall():
            _send_once(conn, row[0], "expired", today_str, send_email_fn)

    conn.close()
    print(f"✅ Billing cron done — {today_str}")


def _send_once(conn, client_id: str, email_type: str, today_str: str, send_fn):
    """Ek hi din mein same email dobara nahi jaayegi."""
    cur2 = conn._conn.cursor()
    try:
        cur2.execute("""
            INSERT INTO email_log (client_id, email_type, sent_at)
            VALUES (%s, %s, %s)
        """, (client_id, email_type, today_str))
        conn._conn.commit()
        send_fn(client_id, email_type)
    except Exception:
        conn._conn.rollback()   # UNIQUE constraint — already sent today


# ════════════════════════════════
# FEATURE GATE CHECK
# ════════════════════════════════

def has_feature(client_id: str, feature_key: str) -> bool:
    """
    Kisi restaurant ke paas yeh feature hai ki nahi.
    Trial mein sab milta hai.
    Active mein plan features + addons check hote hain.
    """
    sub = get_subscription(client_id)
    if not sub:
        return False

    status = sub["status"]

    if status == "expired":
        return False

    if status in ("demo", "trial"):
        return True     # trial mein sab on

    if status in ("active", "grace"):
        plan = get_plan(sub["plan_key"])
        if plan:
            included = plan["features"].get("included", [])
            if feature_key in included:
                return True

        # Addon check
        addons = get_subscription_addons(client_id)
        addon_keys = [a["addon_key"] for a in addons if a["is_active"]]
        return feature_key in addon_keys

    return False


if __name__ == "__main__":
    init_billing_tables()
