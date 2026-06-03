"""
db/core.py — Core restaurant operations
Tables: tables, orders, bills
Includes: table ops, order ops, bill ops, waiter calls, analytics
"""

import json
import csv
import io
import zipfile
import tempfile
import psycopg2.extras
from datetime import datetime, date, timedelta

from db.connection import get_db


# ════════════════════════════════
# INIT
# ════════════════════════════════

def init_core_tables():
    conn = get_db()
    cur = conn._conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            id                SERIAL PRIMARY KEY,
            client_id         TEXT NOT NULL,
            branch_id         TEXT NOT NULL DEFAULT '__default__',
            table_no          INTEGER NOT NULL,
            status            TEXT DEFAULT 'inactive',
            opened_at         TEXT,
            closed_at         TEXT,
            waiter_called_at  TEXT,
            UNIQUE(client_id, branch_id, table_no)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id             SERIAL PRIMARY KEY,
            client_id      TEXT NOT NULL,
            branch_id      TEXT NOT NULL DEFAULT '__default__',
            table_no       INTEGER NOT NULL,
            source         TEXT DEFAULT 'customer',
            customer_name  TEXT,
            customer_phone TEXT,
            customer_id    INTEGER REFERENCES customers(id),
            customer_address TEXT,
            items          TEXT NOT NULL,
            total          INTEGER NOT NULL,
            status         TEXT DEFAULT 'pending',
            ready_items    TEXT DEFAULT '[]',
            created_at     TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            updated_at     TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id             SERIAL PRIMARY KEY,
            client_id      TEXT NOT NULL,
            branch_id      TEXT NOT NULL DEFAULT '__default__',
            table_no       INTEGER NOT NULL,
            order_ids      TEXT NOT NULL,
            customer_name  TEXT,
            customer_phone TEXT,
            subtotal       INTEGER NOT NULL,
            tax            INTEGER DEFAULT 0,
            discount       INTEGER DEFAULT 0,
            total          INTEGER NOT NULL,
            payment_status TEXT DEFAULT 'unpaid',
            payment_mode   TEXT,
            created_at     TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    conn.commit()

    # ── Migrations ──
    migrations = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'customer'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS ready_items TEXT DEFAULT '[]'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS branch_id TEXT DEFAULT '__default__'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES customers(id)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_address TEXT",
        "ALTER TABLE bills ADD COLUMN IF NOT EXISTS branch_id TEXT DEFAULT '__default__'",
        "ALTER TABLE tables ADD COLUMN IF NOT EXISTS branch_id TEXT DEFAULT '__default__'",
        "ALTER TABLE tables ADD COLUMN IF NOT EXISTS waiter_called_at TEXT DEFAULT NULL",
        "ALTER TABLE tables DROP CONSTRAINT IF EXISTS tables_client_id_table_no_key",
    ]
    for sql in migrations:
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            conn._conn.rollback()

    # branch_id backfills
    for sql in [
        "UPDATE orders SET branch_id = '__default__' WHERE branch_id IS NULL",
        "UPDATE bills SET branch_id = '__default__' WHERE branch_id IS NULL",
        "UPDATE tables SET branch_id = '__default__' WHERE branch_id IS NULL",
    ]:
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            conn._conn.rollback()

    # Composite unique constraint on tables
    try:
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'tables_client_id_branch_id_table_no_key'
                ) THEN
                    ALTER TABLE tables ADD CONSTRAINT tables_client_id_branch_id_table_no_key
                    UNIQUE (client_id, branch_id, table_no);
                END IF;
            END $$;
        """)
        conn.commit()
    except Exception:
        conn._conn.rollback()

    conn.close()
    print("[OK] Core tables initialized")


# ════════════════════════════════
# TABLE OPERATIONS
# ════════════════════════════════

def seed_tables(client_id: str, num_tables: int, branch_id: str = "__default__"):
    conn = get_db()
    for i in range(1, num_tables + 1):
        conn.execute("""
            INSERT INTO tables (client_id, branch_id, table_no, status)
            VALUES (%s, %s, %s, 'inactive')
            ON CONFLICT (client_id, branch_id, table_no) DO NOTHING
        """, (client_id, branch_id, i))
    conn.execute("""
        DELETE FROM tables WHERE client_id=%s AND branch_id=%s AND table_no > %s
    """, (client_id, branch_id, num_tables))
    conn.commit()
    conn.close()


def activate_table(client_id: str, table_no: int, branch_id: str = "__default__"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        INSERT INTO tables (client_id, branch_id, table_no, status, opened_at)
        VALUES (%s, %s, %s, 'active', %s)
        ON CONFLICT (client_id, branch_id, table_no)
        DO UPDATE SET status='active', opened_at=%s, closed_at=NULL
    """, (client_id, branch_id, table_no, now, now))
    conn.commit()
    conn.close()


def activate_all_tables(client_id: str, branch_id: str = "__default__"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE tables SET status='active', opened_at=%s, closed_at=NULL
        WHERE client_id=%s AND branch_id=%s
    """, (now, client_id, branch_id))
    conn.commit()
    conn.close()


def close_table(client_id: str, table_no: int, branch_id: str = "__default__"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE tables SET status='inactive', closed_at=%s
        WHERE client_id=%s AND branch_id=%s AND table_no=%s
    """, (now, client_id, branch_id, table_no))
    conn.commit()
    conn.close()


def close_all_tables(client_id: str, branch_id: str = "__default__"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE tables SET status='inactive', closed_at=%s
        WHERE client_id=%s AND branch_id=%s
    """, (now, client_id, branch_id))
    conn.commit()
    conn.close()


def get_table_status(client_id: str, table_no: int, branch_id: str = "__default__"):
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM tables WHERE client_id=%s AND branch_id=%s AND table_no=%s",
        (client_id, branch_id, table_no)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_tables(client_id: str, branch_id: str = "__default__"):
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM tables WHERE client_id=%s AND branch_id=%s ORDER BY table_no",
        (client_id, branch_id)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_table_summary(client_id: str, branch_id: str = "__default__"):
    """
    Returns each table with computed display_status based on current session.
    display_status: inactive | active | occupied | ready | done | billed | paid
    """
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM tables WHERE client_id=%s AND branch_id=%s ORDER BY table_no",
        (client_id, branch_id)
    )
    tables = cur.fetchall()

    result = []
    for t in tables:
        t = dict(t)
        table_no = t["table_no"]

        opened_at = t.get("opened_at") or "1970-01-01 00:00:00"
        opened_at = opened_at.replace("T", " ").split(".")[0]

        cur2 = conn.execute("""
            SELECT id, status FROM orders
            WHERE client_id=%s AND branch_id=%s AND table_no=%s AND status != 'cancelled'
            AND created_at >= %s
        """, (client_id, branch_id, table_no, opened_at))
        orders = [dict(o) for o in cur2.fetchall()]

        cur3 = conn.execute("""
            SELECT id, payment_status, total FROM bills
            WHERE client_id=%s AND branch_id=%s AND table_no=%s AND created_at >= %s
            ORDER BY created_at DESC LIMIT 1
        """, (client_id, branch_id, table_no, opened_at))
        session_bill = cur3.fetchone()
        session_bill = dict(session_bill) if session_bill else None

        paid_order_ids = set()
        cur4 = conn.execute("""
            SELECT order_ids FROM bills
            WHERE client_id=%s AND branch_id=%s AND table_no=%s
            AND payment_status='paid' AND created_at >= %s
        """, (client_id, branch_id, table_no, opened_at))
        for pb in cur4.fetchall():
            paid_order_ids.update(json.loads(pb["order_ids"]))

        unpaid_orders   = [o for o in orders if o["id"] not in paid_order_ids]
        unpaid_statuses = [o["status"] for o in unpaid_orders]

        if not orders:
            display = t["status"]
        elif session_bill and session_bill["payment_status"] == "paid" and not unpaid_orders:
            display = "paid"
        elif session_bill and session_bill["payment_status"] == "unpaid":
            display = "billed"
        elif "ready" in unpaid_statuses:
            display = "ready"
        elif unpaid_statuses and all(s == "done" for s in unpaid_statuses):
            display = "done"
        elif unpaid_statuses:
            display = "occupied"
        else:
            display = "paid"

        t["display_status"]   = display
        t["order_count"]      = len(orders)
        t["opened_at_norm"]   = opened_at
        t["bill_id"]          = session_bill["id"] if session_bill else None
        t["bill_total"]       = session_bill["total"] if session_bill else None
        t["payment_status"]   = session_bill["payment_status"] if session_bill else None
        t["unpaid_done_ids"]  = [o["id"] for o in unpaid_orders if o["status"] == "done"]

        if session_bill and session_bill["payment_status"] == "unpaid":
            try:
                cur5 = conn.execute(
                    "SELECT order_ids FROM bills WHERE id=%s", (session_bill["id"],)
                )
                billed_ids = json.loads(cur5.fetchone()["order_ids"])
            except Exception:
                billed_ids = []
        else:
            billed_ids = []
        t["billed_order_ids"] = billed_ids

        paid_today_ids = []
        try:
            today = date.today().isoformat()
            cur6 = conn.execute(
                "SELECT order_ids FROM bills WHERE client_id=%s AND branch_id=%s AND table_no=%s"
                " AND payment_status='paid' AND DATE(created_at::timestamp)=%s",
                (client_id, branch_id, table_no, today)
            )
            for row in cur6.fetchall():
                paid_today_ids.extend(json.loads(row["order_ids"]))
        except Exception:
            paid_today_ids = []
        t["paid_today_order_ids"] = paid_today_ids

        result.append(t)

    conn.close()
    return result


# ════════════════════════════════
# ORDER OPERATIONS
# ════════════════════════════════

def place_order(client_id: str, table_no: int, items: list,
                total: int, source: str = "customer",
                customer_name: str = None, customer_phone: str = None,
                branch_id: str = "__default__",
                customer_id: int = None, customer_address: str = None):
    conn = get_db()
    cur = conn._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO orders (client_id, branch_id, table_no, source, customer_name, customer_phone,
                            items, total, customer_id, customer_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (client_id, branch_id, table_no, source, customer_name, customer_phone,
          json.dumps(items), total, customer_id, customer_address))
    order_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return order_id


def get_orders(client_id: str, status: str = None, table_no: int = None,
               source: str = None, from_date: str = None, branch_id: str = None):
    conn = get_db()
    query = "SELECT * FROM orders WHERE client_id=%s"
    params = [client_id]
    if branch_id:
        query += " AND branch_id=%s"; params.append(branch_id)
    if status:
        query += " AND status=%s"; params.append(status)
    if table_no:
        query += " AND table_no=%s"; params.append(table_no)
    if source:
        query += " AND source=%s"; params.append(source)
    if from_date:
        query += " AND DATE(created_at::timestamp) >= %s"; params.append(from_date)
    query += " ORDER BY created_at DESC"
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_order_status(order_id: int, status: str):
    conn = get_db()
    conn.execute("""
        UPDATE orders SET status=%s, updated_at=TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        WHERE id=%s
    """, (status, order_id))
    conn.commit()
    conn.close()


def update_ready_items(order_id: int, ready_items: list):
    conn = get_db()
    conn.execute(
        "UPDATE orders SET ready_items=%s, updated_at=TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=%s",
        (json.dumps(ready_items), order_id)
    )
    conn.commit()
    conn.close()


def get_table_orders_detail(client_id: str, table_no: int, branch_id: str = "__default__"):
    """Full orders for current session with billing context"""
    conn = get_db()
    cur = conn.execute(
        "SELECT * FROM tables WHERE client_id=%s AND branch_id=%s AND table_no=%s",
        (client_id, branch_id, table_no)
    )
    table = cur.fetchone()

    opened_at = "1970-01-01 00:00:00"
    if table:
        raw = dict(table).get("opened_at") or "1970-01-01 00:00:00"
        opened_at = raw.replace("T", " ").split(".")[0]

    cur2 = conn.execute("""
        SELECT * FROM orders
        WHERE client_id=%s AND branch_id=%s AND table_no=%s AND created_at >= %s
        ORDER BY created_at DESC
    """, (client_id, branch_id, table_no, opened_at))
    orders = [dict(o) for o in cur2.fetchall()]

    cur3 = conn.execute("""
        SELECT * FROM bills
        WHERE client_id=%s AND branch_id=%s AND table_no=%s AND created_at >= %s
        ORDER BY created_at DESC
    """, (client_id, branch_id, table_no, opened_at))
    bills = [dict(b) for b in cur3.fetchall()]

    for b in bills:
        b["order_ids"] = json.loads(b["order_ids"])

    paid_order_ids = set()
    for b in bills:
        if b["payment_status"] == "paid":
            paid_order_ids.update(b["order_ids"])

    for o in orders:
        o["items"] = json.loads(o["items"])
        o["billed"] = o["id"] in paid_order_ids

    conn.close()
    return {"orders": orders, "bills": bills}


# ════════════════════════════════
# BILL OPERATIONS
# ════════════════════════════════

def generate_bill(client_id: str, table_no: int,
                  customer_name: str = None, customer_phone: str = None,
                  tax_percent: float = 0.0, discount: int = 0,
                  payment_mode: str = None, branch_id: str = "__default__"):
    orders = get_orders(client_id, table_no=table_no, branch_id=branch_id)

    conn = get_db()
    cur = conn.execute("""
        SELECT order_ids FROM bills
        WHERE client_id=%s AND branch_id=%s AND table_no=%s AND payment_status='paid'
    """, (client_id, branch_id, table_no))
    paid_bills = cur.fetchall()
    conn.close()

    already_billed_ids = set()
    for b in paid_bills:
        already_billed_ids.update(json.loads(b["order_ids"]))

    billable = [
        o for o in orders
        if o["status"] == "done" and o["id"] not in already_billed_ids
    ]

    if not billable:
        return None

    order_ids = [o["id"] for o in billable]
    subtotal  = sum(o["total"] for o in billable)
    tax       = int(subtotal * tax_percent / 100)
    total     = subtotal + tax - discount

    conn = get_db()
    cur2 = conn._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur2.execute("""
        INSERT INTO bills (client_id, branch_id, table_no, order_ids, customer_name, customer_phone,
                           subtotal, tax, discount, total, payment_mode)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (client_id, branch_id, table_no, json.dumps(order_ids),
          customer_name, customer_phone,
          subtotal, tax, discount, total, payment_mode))
    bill_id = cur2.fetchone()["id"]
    conn.commit()
    conn.close()

    return {
        "bill_id":        bill_id,
        "client_id":      client_id,
        "branch_id":      branch_id,
        "table_no":       table_no,
        "customer_name":  customer_name,
        "customer_phone": customer_phone,
        "order_ids":      order_ids,
        "subtotal":       subtotal,
        "tax":            tax,
        "discount":       discount,
        "total":          total,
        "payment_mode":   payment_mode,
        "orders":         billable,
    }


def get_bill(bill_id: int):
    conn = get_db()
    cur = conn.execute("SELECT * FROM bills WHERE id=%s", (bill_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    bill = dict(row)
    bill["order_ids"] = json.loads(bill["order_ids"])
    return bill


def mark_bill_paid(bill_id: int, payment_mode: str):
    conn = get_db()
    conn.execute("""
        UPDATE bills SET payment_status='paid', payment_mode=%s WHERE id=%s
    """, (payment_mode, bill_id))
    conn.commit()
    conn.close()


# ════════════════════════════════
# WAITER CALLS
# ════════════════════════════════

def create_waiter_call(client_id: str, table_no: int, branch_id: str = "__default__"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE tables SET waiter_called_at=%s
        WHERE client_id=%s AND branch_id=%s AND table_no=%s
    """, (now, client_id, branch_id, table_no))
    conn.commit()
    conn.close()


def get_active_calls(client_id: str, branch_id: str = "__default__"):
    conn = get_db()
    cur = conn.execute("""
        SELECT table_no, waiter_called_at as called_at
        FROM tables
        WHERE client_id=%s AND branch_id=%s AND waiter_called_at IS NOT NULL
        ORDER BY waiter_called_at ASC
    """, (client_id, branch_id))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_waiter_call(client_id: str, table_no: int, branch_id: str = "__default__"):
    conn = get_db()
    conn.execute("""
        UPDATE tables SET waiter_called_at=NULL
        WHERE client_id=%s AND branch_id=%s AND table_no=%s
    """, (client_id, branch_id, table_no))
    conn.commit()
    conn.close()


# ════════════════════════════════
# ANALYTICS — Owner dashboard
# ════════════════════════════════

def get_summary(client_id: str, branch_id: str = None):
    conn = get_db()
    raw = conn._conn.cursor()
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    raw.execute(f"SELECT COUNT(*) FROM orders WHERE client_id=%s {bf}", (client_id,) + bp)
    total_orders = raw.fetchone()[0]

    raw.execute(
        f"SELECT COALESCE(SUM(total),0) FROM bills WHERE client_id=%s AND payment_status='paid' {bf}",
        (client_id,) + bp
    )
    total_revenue = raw.fetchone()[0]

    raw.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id=%s AND status='pending' {bf}",
        (client_id,) + bp
    )
    pending_orders = raw.fetchone()[0]

    raw.execute(
        f"SELECT COUNT(*) FROM tables WHERE client_id=%s AND status != 'inactive' {bf}",
        (client_id,) + bp
    )
    active_tables = raw.fetchone()[0]

    conn.close()
    return {
        "total_orders":   total_orders,
        "total_revenue":  total_revenue,
        "pending_orders": pending_orders,
        "active_tables":  active_tables,
    }


def get_analytics(client_id: str, branch_id: str = None):
    """Rich analytics for owner dashboard. branch_id=None → entire brand combined."""
    conn = get_db()
    raw = conn._conn.cursor()
    today     = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    raw.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id=%s AND DATE(created_at::timestamp)=%s AND status != 'cancelled' {bf}",
        (client_id, today) + bp
    )
    today_orders = raw.fetchone()[0]

    raw.execute(
        f"SELECT COALESCE(SUM(total),0) FROM bills WHERE client_id=%s AND payment_status='paid' AND DATE(created_at::timestamp)=%s {bf}",
        (client_id, today) + bp
    )
    today_revenue = raw.fetchone()[0]

    raw.execute(
        f"SELECT COUNT(*) FROM bills WHERE client_id=%s AND payment_status='paid' AND DATE(created_at::timestamp)=%s {bf}",
        (client_id, today) + bp
    )
    today_bills = raw.fetchone()[0]

    today_avg = round(today_revenue / today_bills, 0) if today_bills > 0 else 0

    raw.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id=%s AND DATE(created_at::timestamp)=%s AND status != 'cancelled' {bf}",
        (client_id, yesterday) + bp
    )
    yest_orders = raw.fetchone()[0]

    raw.execute(
        f"SELECT COALESCE(SUM(total),0) FROM bills WHERE client_id=%s AND payment_status='paid' AND DATE(created_at::timestamp)=%s {bf}",
        (client_id, yesterday) + bp
    )
    yest_revenue = raw.fetchone()[0]

    def pct_change(today_val, yest_val):
        if yest_val == 0:
            return None
        return round((today_val - yest_val) / yest_val * 100, 1)

    raw.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id=%s AND status != 'cancelled' {bf}", (client_id,) + bp
    )
    alltime_orders = raw.fetchone()[0]

    raw.execute(
        f"SELECT COALESCE(SUM(total),0) FROM bills WHERE client_id=%s AND payment_status='paid' {bf}",
        (client_id,) + bp
    )
    alltime_revenue = raw.fetchone()[0]

    raw.execute(
        f"SELECT COUNT(*) FROM orders WHERE client_id=%s AND status='pending' {bf}", (client_id,) + bp
    )
    pending_now = raw.fetchone()[0]

    raw.execute(
        f"SELECT COUNT(*) FROM tables WHERE client_id=%s AND status != 'inactive' {bf}", (client_id,) + bp
    )
    active_tables = raw.fetchone()[0]

    raw.execute(
        f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' {bf}", (client_id,) + bp
    )
    all_orders_items = raw.fetchall()

    item_counts  = {}
    item_revenue = {}
    for row in all_orders_items:
        try:
            items = json.loads(row[0])
            for it in items:
                name  = it.get("name", "")
                qty   = it.get("qty", 0)
                price = it.get("price", 0)
                item_counts[name]  = item_counts.get(name, 0)  + qty
                item_revenue[name] = item_revenue.get(name, 0) + qty * price
        except Exception:
            pass

    top_items = sorted(
        [{"name": k, "qty": v, "revenue": item_revenue.get(k, 0)} for k, v in item_counts.items()],
        key=lambda x: x["qty"], reverse=True
    )[:8]

    raw.execute(
        f"""SELECT payment_mode, COUNT(*) as cnt, COALESCE(SUM(total),0) as rev
           FROM bills WHERE client_id=%s AND payment_status='paid' {bf}
           GROUP BY payment_mode""",
        (client_id,) + bp
    )
    pay_rows = raw.fetchall()
    payment_breakdown = [{"mode": r[0] or "unknown", "count": r[1], "revenue": r[2]} for r in pay_rows]

    raw.execute(
        f"""SELECT EXTRACT(HOUR FROM created_at::timestamp)::INTEGER as hr, COUNT(*) as cnt
           FROM orders WHERE client_id=%s AND DATE(created_at::timestamp)=%s AND status != 'cancelled' {bf}
           GROUP BY hr ORDER BY hr""",
        (client_id, today) + bp
    )
    hourly_rows = raw.fetchall()
    hourly = {r[0]: r[1] for r in hourly_rows}
    hourly_data = [{"hour": h, "orders": hourly.get(h, 0)} for h in range(8, 24)]

    raw.execute(
        f"""SELECT DATE(created_at::timestamp) as day, COALESCE(SUM(total),0) as rev, COUNT(*) as cnt
           FROM bills WHERE client_id=%s AND payment_status='paid' {bf}
           AND DATE(created_at::timestamp) >= CURRENT_DATE - INTERVAL '6 days'
           GROUP BY day ORDER BY day""",
        (client_id,) + bp
    )
    daily_rows = raw.fetchall()
    daily_map  = {str(r[0]): {"revenue": r[1], "orders": r[2]} for r in daily_rows}
    daily_data = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        daily_data.append({
            "date":    d,
            "label":   (date.today() - timedelta(days=i)).strftime("%a"),
            "revenue": daily_map.get(d, {}).get("revenue", 0),
            "orders":  daily_map.get(d, {}).get("orders",  0),
        })

    raw.execute(
        f"""SELECT source, COUNT(*) as cnt FROM orders
           WHERE client_id=%s AND DATE(created_at::timestamp)=%s AND status != 'cancelled' {bf}
           GROUP BY source""",
        (client_id, today) + bp
    )
    source_rows  = raw.fetchall()
    source_today = {r[0]: r[1] for r in source_rows}

    conn.close()
    return {
        "today": {
            "orders":               today_orders,
            "revenue":              today_revenue,
            "bills_paid":           today_bills,
            "avg_order_value":      int(today_avg),
            "orders_change_pct":    pct_change(today_orders,  yest_orders),
            "revenue_change_pct":   pct_change(today_revenue, yest_revenue),
            "source_breakdown":     source_today,
        },
        "alltime": {
            "orders":        alltime_orders,
            "revenue":       alltime_revenue,
            "pending_now":   pending_now,
            "active_tables": active_tables,
        },
        "top_items":         top_items,
        "payment_breakdown": payment_breakdown,
        "hourly_today":      hourly_data,
        "daily_last7":       daily_data,
    }


# ════════════════════════════════
# CHATBOT ANALYTICS FUNCTIONS
# ════════════════════════════════

def get_today_sales(client_id: str, branch_id: str = None) -> dict:
    conn = get_db()
    raw   = conn._conn.cursor()
    today = date.today().isoformat()
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    raw.execute(
        f"SELECT COALESCE(SUM(total), 0), COUNT(*) FROM bills "
        f"WHERE client_id=%s AND payment_status='paid' AND DATE(created_at::timestamp)=%s {bf}",
        (client_id, today) + bp
    )
    row           = raw.fetchone()
    total_revenue = int(row[0])
    bills_paid    = int(row[1])
    avg_bill      = round(total_revenue / bills_paid) if bills_paid > 0 else 0

    conn.close()
    return {"date": today, "total_revenue": total_revenue, "bills_paid": bills_paid, "avg_bill": avg_bill}


def get_total_orders_today(client_id: str, branch_id: str = None) -> dict:
    conn = get_db()
    raw   = conn._conn.cursor()
    today = date.today().isoformat()
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    raw.execute(
        f"SELECT status, COUNT(*) FROM orders "
        f"WHERE client_id=%s AND DATE(created_at::timestamp)=%s {bf} "
        f"GROUP BY status",
        (client_id, today) + bp
    )
    rows   = raw.fetchall()
    conn.close()
    counts = {r[0]: int(r[1]) for r in rows}
    total  = sum(counts.values())
    return {
        "date":      today,
        "total":     total,
        "pending":   counts.get("pending",   0),
        "done":      counts.get("done",      0),
        "cancelled": counts.get("cancelled", 0),
        "ready":     counts.get("ready",     0),
    }


def get_top_selling_items(client_id: str, limit: int = 5, period: str = "today",
                          branch_id: str = None) -> dict:
    conn = get_db()
    raw   = conn._conn.cursor()
    today = date.today().isoformat()
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    if period == "today":
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' "
            f"AND DATE(created_at::timestamp)=%s {bf}",
            (client_id, today) + bp
        )
    elif period == "week":
        week_start = (date.today() - timedelta(days=6)).isoformat()
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' "
            f"AND DATE(created_at::timestamp) >= %s {bf}",
            (client_id, week_start) + bp
        )
    elif period == "month":
        month_start = (date.today() - timedelta(days=29)).isoformat()
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' "
            f"AND DATE(created_at::timestamp) >= %s {bf}",
            (client_id, month_start) + bp
        )
    else:
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' {bf}",
            (client_id,) + bp
        )

    rows         = raw.fetchall()
    conn.close()
    item_qty     = {}
    item_revenue = {}
    for row in rows:
        try:
            items = json.loads(row[0])
            for it in items:
                name  = it.get("name", "")
                qty   = it.get("qty",   0)
                price = it.get("price", 0)
                item_qty[name]     = item_qty.get(name, 0)     + qty
                item_revenue[name] = item_revenue.get(name, 0) + qty * price
        except Exception:
            pass

    sorted_items = sorted(
        [{"name": k, "qty": v, "revenue": item_revenue.get(k, 0)} for k, v in item_qty.items()],
        key=lambda x: x["qty"], reverse=True
    )[:limit]
    return {"period": period, "items": sorted_items}


def get_lowest_selling_items(client_id: str, limit: int = 5, period: str = "week",
                             branch_id: str = None) -> dict:
    conn = get_db()
    raw   = conn._conn.cursor()
    today = date.today().isoformat()
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    if period == "today":
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' "
            f"AND DATE(created_at::timestamp)=%s {bf}",
            (client_id, today) + bp
        )
    elif period == "week":
        week_start = (date.today() - timedelta(days=6)).isoformat()
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' "
            f"AND DATE(created_at::timestamp) >= %s {bf}",
            (client_id, week_start) + bp
        )
    elif period == "month":
        month_start = (date.today() - timedelta(days=29)).isoformat()
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' "
            f"AND DATE(created_at::timestamp) >= %s {bf}",
            (client_id, month_start) + bp
        )
    else:
        raw.execute(
            f"SELECT items FROM orders WHERE client_id=%s AND status != 'cancelled' {bf}",
            (client_id,) + bp
        )

    rows         = raw.fetchall()
    conn.close()
    item_qty     = {}
    item_revenue = {}
    for row in rows:
        try:
            items = json.loads(row[0])
            for it in items:
                name  = it.get("name", "")
                qty   = it.get("qty",   0)
                price = it.get("price", 0)
                item_qty[name]     = item_qty.get(name, 0)     + qty
                item_revenue[name] = item_revenue.get(name, 0) + qty * price
        except Exception:
            pass

    if not item_qty:
        return {"period": period, "items": []}

    sorted_items = sorted(
        [{"name": k, "qty": v, "revenue": item_revenue.get(k, 0)} for k, v in item_qty.items()],
        key=lambda x: x["qty"]
    )[:limit]
    return {"period": period, "items": sorted_items}


def get_revenue_summary(client_id: str, days: int = 7, branch_id: str = None) -> dict:
    conn = get_db()
    raw  = conn._conn.cursor()
    days = max(1, min(days, 30))
    bf = "AND branch_id=%s" if branch_id else ""
    bp = (branch_id,) if branch_id else ()

    raw.execute(
        f"""
        SELECT DATE(created_at::timestamp) AS day,
               COALESCE(SUM(total), 0)     AS rev,
               COUNT(*)                    AS cnt
        FROM bills
        WHERE client_id=%s
          AND payment_status='paid'
          AND DATE(created_at::timestamp) >= CURRENT_DATE - INTERVAL '%s days'
          {bf}
        GROUP BY day
        ORDER BY day
        """,
        (client_id, days - 1) + bp
    )
    rows      = raw.fetchall()
    conn.close()
    daily_map = {str(r[0]): {"revenue": int(r[1]), "orders": int(r[2])} for r in rows}
    daily_data = []
    for i in range(days - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        daily_data.append({
            "date":    d,
            "label":   (date.today() - timedelta(days=i)).strftime("%a"),
            "revenue": daily_map.get(d, {}).get("revenue", 0),
            "orders":  daily_map.get(d, {}).get("orders",  0),
        })

    return {
        "days":          days,
        "total_revenue": sum(d["revenue"] for d in daily_data),
        "total_orders":  sum(d["orders"]  for d in daily_data),
        "daily":         daily_data,
    }


# ════════════════════════════════
# DB EXPORT
# ════════════════════════════════

def export_full_db_zip() -> str:
    conn = get_db()
    raw  = conn._conn.cursor()

    raw.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    table_names = [r[0] for r in raw.fetchall()]

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()

    NO_ID_TABLES = {"restaurants", "site_settings"}

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for table_name in table_names:
            order_clause = "" if table_name in NO_ID_TABLES else "ORDER BY id"
            raw.execute(f"SELECT * FROM {table_name} {order_clause}")
            rows      = raw.fetchall()
            col_names = [desc[0] for desc in raw.description]
            buf       = io.StringIO()
            writer    = csv.writer(buf)
            writer.writerow(col_names)
            writer.writerows(rows)
            zf.writestr(f"{table_name}.csv", buf.getvalue())

    conn.close()
    return tmp.name
