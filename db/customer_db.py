"""
db/customer.py — Customers (Google OAuth delivery users)
Tables: customers
"""

import json
from db.connection import get_db


# ════════════════════════════════
# INIT
# ════════════════════════════════

def init_customer_tables():
    conn = get_db()
    cur  = conn._conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id         SERIAL PRIMARY KEY,
            google_id  TEXT UNIQUE NOT NULL,
            name       TEXT,
            email      TEXT,
            phone      TEXT,
            address    TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    conn.close()
    print("[OK] Customer tables initialized")


# ════════════════════════════════
# CRUD
# ════════════════════════════════

def get_or_create_customer(google_id: str, name: str, email: str) -> dict:
    """Google login ke baad customer upsert karo — pehli baar create, baad mein fetch"""
    conn = get_db()
    conn.execute("""
        INSERT INTO customers (google_id, name, email)
        VALUES (%s, %s, %s)
        ON CONFLICT (google_id) DO UPDATE
            SET name  = EXCLUDED.name,
                email = EXCLUDED.email
    """, (google_id, name, email))
    conn.commit()
    cur = conn.execute("SELECT * FROM customers WHERE google_id=%s", (google_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row)


def get_customer_by_id(customer_id: int) -> dict | None:
    """Customer by internal ID"""
    conn = get_db()
    cur  = conn.execute("SELECT * FROM customers WHERE id=%s", (customer_id,))
    row  = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_customer_profile(customer_id: int, phone: str, address: str):
    """First time profile complete karo — phone + address save"""
    conn = get_db()
    conn.execute("""
        UPDATE customers SET phone=%s, address=%s WHERE id=%s
    """, (phone, address, customer_id))
    conn.commit()
    conn.close()


def get_customer_orders(customer_id: int) -> list:
    """Customer ki saari delivery orders — history page ke liye"""
    conn = get_db()
    cur  = conn.execute("""
        SELECT o.*,
               r_default.config->'restaurant'->>'name' as restaurant_name,
               r_branch.config->'restaurant'->>'name'  as branch_name
        FROM orders o
        LEFT JOIN restaurants r_default
            ON r_default.client_id = o.client_id AND r_default.branch_id = '__default__'
        LEFT JOIN restaurants r_branch
            ON r_branch.client_id  = o.client_id AND r_branch.branch_id  = o.branch_id
        WHERE o.customer_id=%s AND o.source='delivery'
        ORDER BY o.created_at DESC
    """, (customer_id,))
    rows   = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        row          = dict(r)
        row["items"] = json.loads(row["items"]) if isinstance(row["items"], str) else row["items"]
        result.append(row)
    return result
