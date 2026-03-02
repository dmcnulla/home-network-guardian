from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    ip TEXT,
    hostname TEXT,
    trusted INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credentials_state (
    key TEXT PRIMARY KEY,
    hash_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_device(self, mac: str, ip: str | None, hostname: str | None, trusted: bool) -> None:
        now = utc_now()
        self.conn.execute(
            """
            INSERT INTO devices(mac, ip, hostname, trusted, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET
              ip=excluded.ip,
              hostname=excluded.hostname,
              trusted=excluded.trusted,
              last_seen=excluded.last_seen
            """,
            (mac.lower(), ip, hostname, int(trusted), now, now),
        )
        self.conn.commit()

    def known_macs(self) -> set[str]:
        rows = self.conn.execute("SELECT mac FROM devices").fetchall()
        return {row[0].lower() for row in rows}

    def log_event(
        self,
        event_type: str,
        severity: str,
        source: str,
        message: str,
        metadata_json: str = "{}",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO security_events(event_type, severity, source, message, metadata_json, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_type, severity, source, message, metadata_json, utc_now()),
        )
        self.conn.commit()

    def get_credential_hash(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT hash_value FROM credentials_state WHERE key = ?",
            (key,),
        ).fetchone()
        return row[0] if row else None

    def set_credential_hash(self, key: str, hash_value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO credentials_state(key, hash_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              hash_value=excluded.hash_value,
              updated_at=excluded.updated_at
            """,
            (key, hash_value, utc_now()),
        )
        self.conn.commit()
