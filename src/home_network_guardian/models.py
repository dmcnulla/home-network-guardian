from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Device:
    mac: str
    ip: str | None = None
    hostname: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    trusted: bool = False


@dataclass(slots=True)
class SecurityEvent:
    event_type: str
    severity: str
    source: str
    message: str
    occurred_at: datetime
    metadata_json: str = "{}"
