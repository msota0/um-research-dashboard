import sqlite3
import json
import time
import os
from pathlib import Path


class CacheManager:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL,
                    ttl INTEGER DEFAULT 86400
                )
            """)
            conn.commit()

    def get(self, key: str):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT data, fetched_at, ttl FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            if time.time() - row["fetched_at"] > row["ttl"]:
                return None
            return json.loads(row["data"])

    def set(self, key: str, data, source: str, ttl: int = 86400):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache (key, data, source, fetched_at, ttl)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, json.dumps(data), source, int(time.time()), ttl),
            )
            conn.commit()

    def invalidate(self, key: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    def clear_expired(self):
        now = int(time.time())
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM cache WHERE (fetched_at + ttl) < ?", (now,)
            )
            conn.commit()

    def status(self) -> dict:
        with self._get_conn() as conn:
            now = int(time.time())
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE (fetched_at + ttl) < ?", (now,)
            ).fetchone()[0]
            oldest = conn.execute(
                "SELECT MIN(fetched_at) FROM cache"
            ).fetchone()[0]
            newest = conn.execute(
                "SELECT MAX(fetched_at) FROM cache"
            ).fetchone()[0]
        size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        return {
            "total_entries": total,
            "expired_entries": expired,
            "size_bytes": size,
            "oldest_entry": oldest,
            "newest_entry": newest,
        }
