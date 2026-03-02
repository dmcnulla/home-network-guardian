from home_network_guardian.config import Settings
from home_network_guardian.traffic import TrafficDetector


def test_portscan_detection(tmp_path) -> None:
    f = tmp_path / "events.jsonl"
    lines = []
    for p in range(1, 30):
        lines.append(
            '{"timestamp":"2026-03-01T16:00:00Z","source":"1.2.3.4","kind":"conn","dst_port":%d}' % p
        )
    f.write_text("\n".join(lines), encoding="utf-8")

    s = Settings(malicious_events_file=f, portscan_threshold=25)
    d = TrafficDetector(s)
    alerts = d.detect()
    assert any(a.event_type == "portscan_detected" for a in alerts)
