"""
db/connection.py — PostgreSQL connection pool
Sirf pool, _PgConn, aur get_db() yahan hain.
Baaki saari db/ files yahan se import karti hain.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import psycopg2
import psycopg2.pool
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set!")

_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=50,
    dsn=DATABASE_URL,
    connect_timeout=10
)


class _PgConn:
    """
    Thin wrapper around a psycopg2 connection from the pool.
    Mimics the sqlite3 connection API used throughout the codebase:
      conn.execute(sql, params)  → returns cursor
      conn.commit()
      conn.close()              → returns connection to pool (does NOT close it)
    Row dicts are returned via RealDictCursor, just like sqlite3.Row.
    """

    def __init__(self):
        self._conn = _pool.getconn()
        self._conn.autocommit = False

    def execute(self, sql, params=()):
        try:
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            return cur
        except psycopg2.OperationalError:
            # purana dead connection wapas pool mein do
            try:
                _pool.putconn(self._conn)
            except Exception:
                pass
            # fresh connection lo
            self._conn = _pool.getconn()
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params)
            return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        _pool.putconn(self._conn)


def get_db() -> _PgConn:
    """Return a _PgConn wrapper — callers use it exactly like sqlite3 connection."""
    return _PgConn()
