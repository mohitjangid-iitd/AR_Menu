"""
db/restaurant.py — Restaurant config + trash metadata
Tables: restaurants, trash_meta
"""

import json
from db.connection import get_db


# ════════════════════════════════
# INIT
# ════════════════════════════════

def init_restaurant_tables():
    conn = get_db()
    cur  = conn._conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            client_id   TEXT NOT NULL,
            branch_id   TEXT NOT NULL DEFAULT '__default__',
            config      JSONB NOT NULL,
            theme       JSONB,
            updated_at  TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (client_id, branch_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trash_meta (
            id              SERIAL PRIMARY KEY,
            client_id       TEXT NOT NULL,
            original_name   TEXT NOT NULL,
            original_path   TEXT NOT NULL,
            trash_name      TEXT NOT NULL UNIQUE,
            file_type       TEXT NOT NULL,
            size_kb         REAL DEFAULT 0,
            storage         TEXT DEFAULT 'local',
            deleted_at      TEXT NOT NULL,
            auto_delete_at  TEXT NOT NULL
        )
    """)

    conn.commit()

    # Migrations
    for sql in [
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS branch_id TEXT DEFAULT '__default__'",
        "ALTER TABLE restaurants ADD COLUMN IF NOT EXISTS theme JSONB DEFAULT NULL",
        "ALTER TABLE restaurants DROP CONSTRAINT IF EXISTS restaurants_pkey",
    ]:
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            conn._conn.rollback()

    try:
        cur.execute("UPDATE restaurants SET branch_id = '__default__' WHERE branch_id IS NULL")
        conn.commit()
    except Exception:
        conn._conn.rollback()

    # Composite PK
    try:
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'restaurants_pkey'
                ) THEN
                    ALTER TABLE restaurants ADD PRIMARY KEY (client_id, branch_id);
                END IF;
            END $$;
        """)
        conn.commit()
    except Exception:
        conn._conn.rollback()

    conn.close()
    print("[OK] Restaurant tables initialized")


# ════════════════════════════════
# RESTAURANT CONFIG
# ════════════════════════════════

def save_restaurant_json(client_id: str, data: dict, branch_id: str = "__default__"):
    """
    Restaurant config DB mein save karo (upsert).
    - theme  → alag column mein jaati hai (sirf __default__ row pe)
    - subscription → bilkul nahi jaayegi config mein (subscriptions table mein manage hoti hai)
    """
    theme        = data.get("theme", None)
    config_clean = {k: v for k, v in data.items() if k not in ("theme", "subscription")}

    conn = get_db()
    if theme is not None:
        conn.execute("""
            INSERT INTO restaurants (client_id, branch_id, config, theme, updated_at)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, NOW())
            ON CONFLICT (client_id, branch_id)
            DO UPDATE SET config = EXCLUDED.config, theme = EXCLUDED.theme, updated_at = NOW()
        """, (client_id, branch_id,
              json.dumps(config_clean, ensure_ascii=False),
              json.dumps(theme,        ensure_ascii=False)))
    else:
        conn.execute("""
            INSERT INTO restaurants (client_id, branch_id, config, updated_at)
            VALUES (%s, %s, %s::jsonb, NOW())
            ON CONFLICT (client_id, branch_id)
            DO UPDATE SET config = EXCLUDED.config, updated_at = NOW()
        """, (client_id, branch_id,
              json.dumps(config_clean, ensure_ascii=False)))
    conn.commit()
    conn.close()


def get_restaurant_branches(client_id: str) -> list:
    """Ek brand ki saari branches"""
    conn = get_db()
    cur  = conn.execute(
        "SELECT branch_id, config, theme FROM restaurants WHERE client_id=%s ORDER BY branch_id",
        (client_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_restaurant_full(client_id: str):
    """Poora restaurant delete — DB se sab (billing tables bhi)"""
    conn = get_db()
    for sql in [
        ("DELETE FROM orders WHERE client_id=%s",               (client_id,)),
        ("DELETE FROM bills WHERE client_id=%s",                (client_id,)),
        ("DELETE FROM tables WHERE client_id=%s",               (client_id,)),
        ("DELETE FROM staff WHERE client_id=%s",                (client_id,)),
        ("DELETE FROM restaurants WHERE client_id=%s",          (client_id,)),
        ("DELETE FROM subscription_addons WHERE client_id=%s",  (client_id,)),
        ("DELETE FROM payment_history WHERE client_id=%s",      (client_id,)),
        ("DELETE FROM email_log WHERE client_id=%s",            (client_id,)),
        ("DELETE FROM subscriptions WHERE client_id=%s",        (client_id,)),
    ]:
        conn.execute(sql[0], sql[1])
    conn.commit()
    conn.close()


# ════════════════════════════════
# TRASH META
# ════════════════════════════════

def trash_add(entry: dict):
    """
    Naya trash entry DB mein insert karo.
    entry keys: client_id, original_name, original_path, trash_name,
                file_type, size_kb, storage, deleted_at, auto_delete_at
    """
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO trash_meta
                (client_id, original_name, original_path, trash_name,
                 file_type, size_kb, storage, deleted_at, auto_delete_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trash_name) DO NOTHING
        """, (
            entry["client_id"],
            entry["original_name"],
            entry["original_path"],
            entry["trash_name"],
            entry["file_type"],
            entry.get("size_kb", 0),
            entry.get("storage", "local"),
            entry["deleted_at"],
            entry["auto_delete_at"],
        ))
        conn.commit()
    finally:
        conn.close()


def trash_get_all(client_id: str = None) -> list:
    """Saari trash entries — client_id dene pe filter hogi."""
    conn = get_db()
    if client_id:
        cur = conn.execute(
            "SELECT * FROM trash_meta WHERE client_id=%s ORDER BY deleted_at DESC",
            (client_id,)
        )
    else:
        cur = conn.execute("SELECT * FROM trash_meta ORDER BY deleted_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def trash_get_one(trash_name: str) -> dict | None:
    conn = get_db()
    cur  = conn.execute("SELECT * FROM trash_meta WHERE trash_name=%s", (trash_name,))
    row  = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def trash_remove(trash_name: str):
    conn = get_db()
    conn.execute("DELETE FROM trash_meta WHERE trash_name=%s", (trash_name,))
    conn.commit()
    conn.close()


def trash_remove_by_client(client_id: str):
    conn = get_db()
    conn.execute("DELETE FROM trash_meta WHERE client_id=%s", (client_id,))
    conn.commit()
    conn.close()


def trash_remove_all():
    conn = get_db()
    conn.execute("DELETE FROM trash_meta")
    conn.commit()
    conn.close()


def trash_remove_expired(before_datetime_str: str) -> list:
    """
    auto_delete_at < before_datetime_str wali entries return karke delete karo.
    Returns list of expired entries (taaki caller file bhi delete kar sake).
    """
    conn     = get_db()
    cur      = conn.execute(
        "SELECT * FROM trash_meta WHERE auto_delete_at < %s",
        (before_datetime_str,)
    )
    expired  = [dict(r) for r in cur.fetchall()]
    if expired:
        conn.execute(
            "DELETE FROM trash_meta WHERE auto_delete_at < %s",
            (before_datetime_str,)
        )
        conn.commit()
    conn.close()
    return expired
