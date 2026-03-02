# Home Network Guardian

A Python-based home network monitoring project for macOS focused on:

1. **MAC inventory tracking** and alerting when a new address appears.
2. **Malicious traffic detection** with automatic source blocking (safe or enforce mode).
3. **Credential/password-change detection** from snapshot/config diffs.
4. Notifications by **email** and optional **Telegram**.

## Safety and legal notes

- Use only on networks and devices you own or are explicitly authorized to monitor.
- Blocking requires elevated privileges and can interrupt legitimate traffic.
- Start in **safe mode** to validate detections before enabling enforce mode.

## Project structure

- `src/home_network_guardian/cli.py` - CLI commands (`hng scan-once`, `hng daemon`, `hng init-baseline`)
- `src/home_network_guardian/discovery.py` - MAC/IP discovery via `arp -an`
- `src/home_network_guardian/traffic.py` - stream-based malicious event detection
- `src/home_network_guardian/blocker.py` - block action runner
- `src/home_network_guardian/credential_monitor.py` - credential/config hash monitoring
- `src/home_network_guardian/db.py` - SQLite persistence
- `src/home_network_guardian/notifier.py` - Email + Telegram alerts
- `src/home_network_guardian/engine.py` - orchestrates monitoring cycle

## Setup (macOS)

1. Open terminal in this project directory.
2. Create environment and install:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e .[dev]`
3. Configure environment:
   - `cp .env.example .env`
   - Update `.env` values for your network and notifications.

## Quick start

1. Initialize baseline inventory:
   - `hng init-baseline`
2. Run one cycle:
   - `hng scan-once`
3. Run continuously:
   - `hng daemon`

## Config highlights

- `HNG_MODE=safe|enforce`
  - `safe`: logs and alerts block actions only.
  - `enforce`: executes `HNG_BLOCK_COMMAND`.
- `HNG_ALLOWED_MACS=aa:bb:cc:dd:ee:ff,...`
  - Mark known trusted devices.
- `HNG_MALICIOUS_EVENTS_FILE=./data/malicious_events.jsonl`
  - JSONL event feed for traffic detections.
- `HNG_CREDENTIAL_SNAPSHOT_PATH` and `HNG_DEVICE_CONFIG_PATH`
  - Files whose hash changes are treated as credential/config changes.

## Malicious event feed format

Append newline-delimited JSON events to `HNG_MALICIOUS_EVENTS_FILE`:

- Connection event:
  - `{"timestamp":"2026-03-01T16:30:00Z","source":"192.168.1.20","kind":"conn","dst_port":22}`
- Failed auth event:
  - `{"timestamp":"2026-03-01T16:31:00Z","source":"192.168.1.20","kind":"auth_fail","service":"ssh"}`
- Direct threat event:
  - `{"timestamp":"2026-03-01T16:31:10Z","source":"192.168.1.20","kind":"threat","message":"Known bad IOC"}`

## Password-change detection model

This project detects likely password/credential changes by hashing JSON states from:

- `HNG_CREDENTIAL_SNAPSHOT_PATH`
- `HNG_DEVICE_CONFIG_PATH`

When hashes change after baseline, it generates a high-severity alert. You can feed these files using:

- Router exports (admin config snapshots)
- Device controller API snapshots
- Password manager export metadata (without secrets)

## Additional feature recommendations

1. Router API integrations (UniFi/OPNsense/pfSense) for direct event ingestion.
2. DHCP lease monitoring to enrich unknown MAC alerts with vendor lookup.
3. Threat intel enrichment (AbuseIPDB/VirusTotal) before auto-blocking.
4. SIEM/webhook output (Slack/Teams/Home Assistant).
5. Quarantine VLAN workflow for suspicious trusted devices.
6. Asset fingerprinting (OS + service baseline) to detect drift.
7. Immutable event log shipping and backup.
8. Rule tuning profile by time-of-day and known behavior patterns.

## Testing

- `pytest`

## Important

Default mode is **safe**. Validate detections and block command behavior before switching to enforce mode.
