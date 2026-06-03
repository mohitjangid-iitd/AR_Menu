"""
db/owner.py — Restaurant owners + signup requests
Tables: owner_signup_requests, owners

Lifecycle:
  1. Owner form submit karta hai → owner_signup_requests (pending)
  2. Admin approve karta hai    → owners row create hota hai
"""

import bcrypt
import psycopg2.extras
from datetime import datetime
from db.connection import get_db


# ════════════════════════════════
# INIT
# ════════════════════════════════

def init_owner_tables():
    conn = get_db()
    cur  = conn._conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS owner_signup_requests (
            id                SERIAL PRIMARY KEY,
            name              TEXT NOT NULL,
            phone             TEXT NOT NULL,
            email             TEXT NOT NULL,
            restaurant_name   TEXT NOT NULL,
            comment           TEXT,
            status            TEXT DEFAULT 'pending',
            client_id         TEXT,
            rejection_reason  TEXT,
            created_at        TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            reviewed_at       TEXT,
            reviewed_by       TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS owners (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            phone         TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            client_id     TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active     INTEGER DEFAULT 1,
            request_id    INTEGER REFERENCES owner_signup_requests(id),
            created_at    TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    conn.commit()
    conn.close()
    print("[OK] Owner tables initialized")


# ════════════════════════════════
# SIGNUP REQUESTS
# ════════════════════════════════

def create_signup_request(name: str, phone: str, email: str,
                          restaurant_name: str, comment: str = None) -> int:
    """Naya owner signup request create karo — pending status mein"""
    conn = get_db()
    cur  = conn._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO owner_signup_requests
            (name, phone, email, restaurant_name, comment)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (name, phone, email, restaurant_name, comment))
    req_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return req_id


def get_signup_requests(status: str = None) -> list:
    """Saari signup requests — status filter optional (pending/approved/rejected)"""
    conn = get_db()
    if status:
        cur = conn.execute(
            "SELECT * FROM owner_signup_requests WHERE status=%s ORDER BY created_at DESC",
            (status,)
        )
    else:
        cur = conn.execute(
            "SELECT * FROM owner_signup_requests ORDER BY created_at DESC"
        )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_signup_request(req_id: int) -> dict | None:
    """Ek specific request by id"""
    conn = get_db()
    cur  = conn.execute(
        "SELECT * FROM owner_signup_requests WHERE id=%s", (req_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def approve_signup_request(req_id: int, client_id: str, reviewed_by: str):
    """Request approve karo — client_id assign karo"""
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE owner_signup_requests
        SET status='approved', client_id=%s, reviewed_at=%s, reviewed_by=%s
        WHERE id=%s
    """, (client_id, now, reviewed_by, req_id))
    conn.commit()
    conn.close()


def reject_signup_request(req_id: int, rejection_reason: str, reviewed_by: str):
    """Request reject karo"""
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute("""
        UPDATE owner_signup_requests
        SET status='rejected', rejection_reason=%s, reviewed_at=%s, reviewed_by=%s
        WHERE id=%s
    """, (rejection_reason, now, reviewed_by, req_id))
    conn.commit()
    conn.close()


# ════════════════════════════════
# OWNERS
# ════════════════════════════════

def create_owner(name: str, phone: str, email: str, client_id: str,
                 password: str, request_id: int = None) -> bool:
    """
    Naya owner account banao — admin approve karne ke baad call hoga.
    username = client_id (login ke liye)
    """
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO owners (name, phone, email, client_id, password_hash, request_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, phone, email, client_id, password_hash, request_id))
        conn.commit()
        return True
    except Exception:
        return False  # email/client_id already exists
    finally:
        conn.close()


def verify_owner(client_id: str, password: str) -> dict | None:
    """
    Owner login verify karo.
    client_id = username (restaurant ka unique id)
    """
    conn = get_db()
    cur  = conn.execute("""
        SELECT * FROM owners WHERE client_id=%s AND is_active=1
    """, (client_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    owner = dict(row)
    if bcrypt.checkpw(password.encode(), owner["password_hash"].encode()):
        owner["role"]          = "owner"
        owner["restaurant_id"] = owner["client_id"]  # auth.py compatibility
        return owner
    return None


def get_owner_by_client_id(client_id: str) -> dict | None:
    """Owner info by client_id"""
    conn = get_db()
    cur  = conn.execute(
        "SELECT id, name, phone, email, client_id, is_active, created_at FROM owners WHERE client_id=%s",
        (client_id,)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def toggle_owner_active(owner_id: int, is_active: bool):
    conn = get_db()
    conn.execute("UPDATE owners SET is_active=%s WHERE id=%s", (int(is_active), owner_id))
    conn.commit()
    conn.close()


def update_owner_password(owner_id: int, new_password: str):
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    conn.execute("UPDATE owners SET password_hash=%s WHERE id=%s", (password_hash, owner_id))
    conn.commit()
    conn.close()
