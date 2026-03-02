from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HNG_", extra="ignore")

    db_path: Path = Path("./data/hng.sqlite3")
    scan_interval_seconds: int = 60
    mode: str = Field(default="safe", pattern="^(safe|enforce)$")

    arp_command: str = "arp -an"
    allowed_macs: str = ""

    malicious_events_file: Path = Path("./data/malicious_events.jsonl")
    portscan_threshold: int = 25
    failed_auth_threshold: int = 8
    block_command: str = "sudo pfctl -t hng_blocklist -T add {source}"

    credential_snapshot_path: Path = Path("./data/credential_snapshot.json")
    device_config_path: Path = Path("./data/device_configs.json")

    notify_email_enabled: bool = False
    notify_email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    notify_telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    def allowed_macs_set(self) -> set[str]:
        return {m.strip().lower() for m in self.allowed_macs.split(",") if m.strip()}
