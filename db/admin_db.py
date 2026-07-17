"""
db/admin.py — Platform admins + site settings + admin-level analytics
Tables: admins, site_settings
"""

import json
import bcrypt
from datetime import date, timedelta
from db.connection import get_db


# ════════════════════════════════
# INIT
# ════════════════════════════════

def init_admin_tables():
    with get_db() as conn:
        cur  = conn._conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id            SERIAL PRIMARY KEY,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                name          TEXT NOT NULL,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)


        # Default feature flags
        try:
            cur.execute("""
                INSERT INTO site_settings (key, value)
                VALUES
                    ('image_to_menu_enabled', 'true'),
                    ('chatbot_enabled',       'true'),
                    ('blog_owner_enabled',    'true'),
                    ('blog_blogger_enabled',  'true')
                ON CONFLICT (key) DO NOTHING
            """)
        except Exception:
            conn._conn.rollback()

        print("[OK] Admin tables initialized")


# ════════════════════════════════
# AUTH
# ════════════════════════════════

def create_admin(username: str, password: str, name: str) -> bool:
    """Site admin banao"""
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO admins (username, password_hash, name)
                VALUES (%s, %s, %s)
            """, (username, password_hash, name))
            return True
        except Exception:
            return False


def verify_admin(username: str, password: str) -> dict | None:
    with get_db() as conn:
        cur = conn.execute("""
            SELECT * FROM admins WHERE LOWER(username)=LOWER(%s) AND is_active=1
        """, (username,))
        row = cur.fetchone()
        if not row:
            return None
        admin = dict(row)
        if bcrypt.checkpw(password.encode(), admin["password_hash"].encode()):
            admin["role"] = "admin"
            return admin
        return None


# ════════════════════════════════
# SITE SETTINGS
# ════════════════════════════════

def get_site_setting(key: str, default=None):
    """Site-level setting fetch karo"""
    with get_db() as conn:
        cur = conn.execute("SELECT value FROM site_settings WHERE key=%s", (key,))
        row = cur.fetchone()
        if not row:
            return default
        val = row["value"]
        if val == "true":  return True
        if val == "false": return False
        return val


def set_site_setting(key: str, value):
    """Site-level setting save karo"""
    if isinstance(value, bool):
        store_val = str(value).lower()
    elif isinstance(value, (list, dict)):
        store_val = json.dumps(value, ensure_ascii=False)
    else:
        store_val = str(value)
    with get_db() as conn:
        conn.execute("""
            INSERT INTO site_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
        """, (key, store_val))


def get_all_site_settings() -> dict:
    """Saari site settings ek saath"""
    with get_db() as conn:
        cur = conn.execute("SELECT key, value FROM site_settings ORDER BY key")
        rows = cur.fetchall()
        result = {}
        for r in rows:
            val = r["value"]
            if val == "true":  result[r["key"]] = True
            elif val == "false": result[r["key"]] = False
            else: result[r["key"]] = val
        return result


# ════════════════════════════════
# PLATFORM-LEVEL ANALYTICS
# ════════════════════════════════

def get_overall_stats() -> dict:
    """Poore platform ki stats"""
    with get_db() as conn:
        raw   = conn._conn.cursor()
        today = date.today().isoformat()

        raw.execute("SELECT COUNT(*) FROM restaurants")
        total_restaurants = raw.fetchone()[0]

        raw.execute("SELECT COUNT(*) FROM staff WHERE is_active=1")
        total_staff = raw.fetchone()[0]

        raw.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at::timestamp)=%s AND status != 'cancelled'",
            (today,)
        )
        today_orders = raw.fetchone()[0]

        raw.execute(
            "SELECT COALESCE(SUM(total),0) FROM bills WHERE payment_status='paid' AND DATE(created_at::timestamp)=%s",
            (today,)
        )
        today_revenue = raw.fetchone()[0]

        raw.execute("SELECT COALESCE(SUM(total),0) FROM bills WHERE payment_status='paid'")
        alltime_revenue = raw.fetchone()[0]

        raw.execute("SELECT COUNT(*) FROM orders WHERE status != 'cancelled'")
        alltime_orders = raw.fetchone()[0]

        return {
            "total_restaurants": total_restaurants,
            "total_staff":       total_staff,
            "today_orders":      today_orders,
            "today_revenue":     today_revenue,
            "alltime_revenue":   alltime_revenue,
            "alltime_orders":    alltime_orders,
        }


def get_top_dishes_overall(limit: int = 10, period: str = "alltime") -> list:
    """Saare restaurants ke top dishes — period: alltime | today | week | month"""
    with get_db() as conn:
        raw   = conn._conn.cursor()
        today = date.today().isoformat()

        if period == "today":
            raw.execute(
                "SELECT items FROM orders WHERE status != 'cancelled' AND DATE(created_at::timestamp) = %s",
                (today,)
            )
        elif period == "week":
            week_start = (date.today() - timedelta(days=6)).isoformat()
            raw.execute(
                "SELECT items FROM orders WHERE status != 'cancelled' AND DATE(created_at::timestamp) >= %s",
                (week_start,)
            )
        elif period == "month":
            month_start = (date.today() - timedelta(days=29)).isoformat()
            raw.execute(
                "SELECT items FROM orders WHERE status != 'cancelled' AND DATE(created_at::timestamp) >= %s",
                (month_start,)
            )
        else:
            raw.execute("SELECT items FROM orders WHERE status != 'cancelled'")

        rows = raw.fetchall()

        item_counts  = {}
        item_revenue = {}
        for row in rows:
            try:
                items = json.loads(row[0])
                for it in items:
                    name  = it.get("name", "")
                    qty   = it.get("qty",  0)
                    price = it.get("price", 0)
                    item_counts[name]  = item_counts.get(name, 0)  + qty
                    item_revenue[name] = item_revenue.get(name, 0) + qty * price
            except Exception:
                pass

        return sorted(
            [{"name": k, "qty": v, "revenue": item_revenue.get(k, 0)} for k, v in item_counts.items()],
            key=lambda x: x["qty"], reverse=True
        )[:limit]


def get_all_restaurants_info() -> list:
    """Saare restaurants ki basic info + staff count + today orders"""
    with get_db() as conn:
        raw   = conn._conn.cursor()
        today = date.today().isoformat()

        raw.execute("""
            SELECT r.client_id, r.config, s.status, s.plan_key, s.final_price, s.period
            FROM restaurants r
            LEFT JOIN subscriptions s ON s.client_id = r.client_id
            WHERE r.branch_id = '__default__'
            ORDER BY r.client_id
        """)
        rows = raw.fetchall()

        restaurants = []
        for row in rows:
            client_id = row[0]
            rdata     = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            rinfo     = rdata.get("restaurant", {})

            raw.execute("SELECT COUNT(*) FROM staff WHERE client_id=%s", (client_id,))
            staff_count = raw.fetchone()[0]

            raw.execute(
                "SELECT COUNT(*) FROM orders WHERE client_id=%s AND DATE(created_at::timestamp)=%s AND status != 'cancelled'",
                (client_id, today)
            )
            today_orders = raw.fetchone()[0]

            raw.execute(
                "SELECT COALESCE(SUM(total),0) FROM bills WHERE client_id=%s AND payment_status='paid' AND DATE(created_at::timestamp)=%s",
                (client_id, today)
            )
            today_revenue = raw.fetchone()[0]

            raw.execute(
                "SELECT COALESCE(SUM(total),0) FROM bills WHERE client_id=%s AND payment_status='paid'",
                (client_id,)
            )
            alltime_revenue = raw.fetchone()[0]

            restaurants.append({
                "client_id":       client_id,
                "name":            rinfo.get("name", client_id),
                "cuisine_type":    rinfo.get("cuisine_type", ""),
                "phone":           rinfo.get("phone", ""),
                "num_tables":      rinfo.get("num_tables", 0),
                "staff_count":     staff_count,
                "today_orders":    today_orders,
                "today_revenue":   today_revenue,
                "alltime_revenue": alltime_revenue,
                "sub_status":  row[2] or "trial",
                "sub_plan":    row[3] or "basic",
                "sub_price":   int(row[4]) if row[4] else 0,
                "sub_period":  row[5] or "monthly",
            })

        return restaurants
