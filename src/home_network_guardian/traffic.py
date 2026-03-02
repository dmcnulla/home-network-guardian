from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from home_network_guardian.config import Settings


@dataclass(slots=True)
class TrafficAlert:
    event_type: str
    source: str
    severity: str
    message: str


class TrafficDetector:
    """
    Reads newline-delimited JSON events from `malicious_events_file`.
    Expected schema per line:
    {"timestamp":"2026-03-01T16:30:00Z","source":"192.168.1.20","kind":"conn","dst_port":22}
    {"timestamp":"...","source":"192.168.1.20","kind":"auth_fail","service":"ssh"}
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._offset = 0
        self._ports_seen: dict[str, deque[tuple[datetime, int]]] = defaultdict(deque)
        self._failed_auths: dict[str, deque[datetime]] = defaultdict(deque)

    def detect(self) -> list[TrafficAlert]:
        events = self._read_new_events(self.settings.malicious_events_file)
        alerts: list[TrafficAlert] = []
        for event in events:
            source = str(event.get("source", "unknown"))
            ts = self._parse_ts(event.get("timestamp"))
            kind = event.get("kind")

            if kind == "conn" and "dst_port" in event:
                dst_port = int(event["dst_port"])
                alerts.extend(self._check_portscan(source, ts, dst_port))

            if kind == "auth_fail":
                alerts.extend(self._check_failed_auth(source, ts))

            if kind == "threat":
                message = str(event.get("message", "Threat intel match"))
                alerts.append(
                    TrafficAlert(
                        event_type="malicious_traffic",
                        source=source,
                        severity="high",
                        message=message,
                    )
                )
        return alerts

    def _check_portscan(self, source: str, ts: datetime, dst_port: int) -> list[TrafficAlert]:
        window = timedelta(minutes=2)
        q = self._ports_seen[source]
        q.append((ts, dst_port))
        while q and ts - q[0][0] > window:
            q.popleft()

        unique_ports = {p for _, p in q}
        if len(unique_ports) >= self.settings.portscan_threshold:
            q.clear()
            return [
                TrafficAlert(
                    event_type="portscan_detected",
                    source=source,
                    severity="high",
                    message=f"Possible port scan from {source} ({len(unique_ports)} ports / 2m)",
                )
            ]
        return []

    def _check_failed_auth(self, source: str, ts: datetime) -> list[TrafficAlert]:
        window = timedelta(minutes=5)
        q = self._failed_auths[source]
        q.append(ts)
        while q and ts - q[0] > window:
            q.popleft()

        if len(q) >= self.settings.failed_auth_threshold:
            q.clear()
            return [
                TrafficAlert(
                    event_type="bruteforce_detected",
                    source=source,
                    severity="high",
                    message=f"Possible brute-force from {source} ({self.settings.failed_auth_threshold}+ auth failures / 5m)",
                )
            ]
        return []

    def _read_new_events(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        if not content:
            return []
        new_blob = content[self._offset :]
        self._offset = len(content)
        events: list[dict] = []
        for line in new_blob.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    events.append(payload)
            except json.JSONDecodeError:
                continue
        return events

    @staticmethod
    def _parse_ts(value: object) -> datetime:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(tz=timezone.utc)
