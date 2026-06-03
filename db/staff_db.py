"""
db/staff.py — Staff accounts
Tables: staff
"""

import bcrypt
from db.connection import get_db


# ════════════════════════════════
# INIT
# ════════════════════════════════

def init_staff_tables():
    conn = get_db()
    cur  = conn._conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id            SERIAL PRIMARY KEY,
            client_id     TEXT NOT NULL,
            branch_id     TEXT NOT NULL DEFAULT '__default__',
            username      TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            name          TEXT NOT NULL,
            role          TEXT NOT NULL,
            is_active     INTEGER DEFAULT 1,
            created_at    TEXT DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            UNIQUE(client_id, username)
        )
    """)
    conn.commit()

    # Migrations
    for sql in [
        "ALTER TABLE staff RENAME COLUMN restaurant_id TO client_id",
        "ALTER TABLE staff DROP COLUMN IF EXISTS branch_ids",
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS branch_id TEXT DEFAULT '__default__'",
    ]:
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            conn._conn.rollback()

    try:
        cur.execute("UPDATE staff SET branch_id = '__default__' WHERE branch_id IS NULL")
        conn.commit()
    except Exception:
        conn._conn.rollback()

    conn.close()
    print("[OK] Staff tables initialized")


# ════════════════════════════════
# AUTH
# ════════════════════════════════

def create_staff(client_id: str, username: str, password: str,
                 name: str, role: str, branch_id: str = "__default__") -> bool:
    """Naya staff member banao — password hash karke store hoga"""
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO staff (client_id, branch_id, username, password_hash, name, role)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (client_id, branch_id, username, password_hash, name, role))
        conn.commit()
        return True
    except Exception:
        return False  # username already exists
    finally:
        conn.close()


def verify_staff(client_id: str, username: str, password: str) -> dict | None:
    """Staff login verify karo — match hone pe staff dict return karo"""
    conn = get_db()
    cur = conn.execute("""
        SELECT * FROM staff
        WHERE client_id=%s AND LOWER(username)=LOWER(%s) AND is_active=1
    """, (client_id, username))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    staff = dict(row)
    # backward compat — purane rows mein restaurant_id column ho sakta hai
    if "client_id" not in staff and "restaurant_id" in staff:
        staff["client_id"] = staff["restaurant_id"]
    if bcrypt.checkpw(password.encode(), staff["password_hash"].encode()):
        return staff
    return None


# ════════════════════════════════
# CRUD
# ════════════════════════════════

def get_staff_list(client_id: str, branch_id: str = None) -> list:
    """Ek restaurant ke saare staff members — branch filter optional"""
    conn = get_db()
    if branch_id:
        cur = conn.execute("""
            SELECT id, client_id, branch_id, username, name, role, is_active, created_at
            FROM staff WHERE client_id=%s AND branch_id=%s ORDER BY role, name
        """, (client_id, branch_id))
    else:
        cur = conn.execute("""
            SELECT id, client_id, branch_id, username, name, role, is_active, created_at
            FROM staff WHERE client_id=%s ORDER BY role, name
        """, (client_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_staff_password(staff_id: int, new_password: str):
    password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = get_db()
    conn.execute("UPDATE staff SET password_hash=%s WHERE id=%s", (password_hash, staff_id))
    conn.commit()
    conn.close()


def toggle_staff_active(staff_id: int, is_active: bool):
    conn = get_db()
    conn.execute("UPDATE staff SET is_active=%s WHERE id=%s", (int(is_active), staff_id))
    conn.commit()
    conn.close()


def delete_staff(staff_id: int):
    conn = get_db()
    conn.execute("DELETE FROM staff WHERE id=%s", (staff_id,))
    conn.commit()
    conn.close()
