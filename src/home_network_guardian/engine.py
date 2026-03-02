from __future__ import annotations

import json
import logging
import time

from home_network_guardian.blocker import Blocker
from home_network_guardian.config import Settings
from home_network_guardian.credential_monitor import detect_credential_change, load_json
from home_network_guardian.db import Database
from home_network_guardian.discovery import discover_devices
from home_network_guardian.notifier import Notifier
from home_network_guardian.traffic import TrafficDetector


logger = logging.getLogger(__name__)


class GuardianEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.db_path)
        self.notifier = Notifier(settings)
        self.blocker = Blocker(settings)
        self.traffic_detector = TrafficDetector(settings)

    def run_once(self) -> None:
        self._scan_devices()
        self._check_traffic()
        self._check_credentials()

    def run_forever(self) -> None:
        logger.info("Starting daemon mode with interval=%ss", self.settings.scan_interval_seconds)
        while True:
            try:
                self.run_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Guardian cycle failed: %s", exc)
            time.sleep(self.settings.scan_interval_seconds)

    def _scan_devices(self) -> None:
        known = self.db.known_macs()
        allowed = self.settings.allowed_macs_set()
        observed = discover_devices(self.settings.arp_command)

        for device in observed:
            trusted = device.mac in allowed
            self.db.upsert_device(device.mac, device.ip, None, trusted)

            if device.mac not in known:
                message = f"New MAC detected: {device.mac} (ip={device.ip or 'unknown'})"
                self.db.log_event("new_mac_detected", "medium", device.mac, message)
                self.notifier.send("[HNG] New device detected", message)
                logger.warning(message)

    def _check_traffic(self) -> None:
        alerts = self.traffic_detector.detect()
        for alert in alerts:
            self.db.log_event(
                event_type=alert.event_type,
                severity=alert.severity,
                source=alert.source,
                message=alert.message,
                metadata_json=json.dumps({"mode": self.settings.mode}),
            )
            ok, detail = self.blocker.block_source(alert.source)
            msg = f"{alert.message}\nAction: {detail}"
            self.notifier.send("[HNG] Malicious traffic alert", msg)
            if ok:
                logger.warning("Blocked or queued block for %s", alert.source)
            else:
                logger.error("Block failed for %s: %s", alert.source, detail)

    def _check_credentials(self) -> None:
        checks = {
            "credential_snapshot": load_json(self.settings.credential_snapshot_path),
            "device_configs": load_json(self.settings.device_config_path),
        }

        for key, state in checks.items():
            previous = self.db.get_credential_hash(key)
            changed, current_hash = detect_credential_change(previous, state)
            self.db.set_credential_hash(key, current_hash)
            if changed:
                message = f"Credential/config change detected for {key}. Verify if expected."
                self.db.log_event("credential_change_detected", "high", key, message)
                self.notifier.send("[HNG] Credential change detected", message)
                logger.warning(message)
