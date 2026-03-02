from home_network_guardian.credential_monitor import detect_credential_change


def test_change_detection() -> None:
    changed, h1 = detect_credential_change(None, {"router": "x"})
    assert not changed

    changed, h2 = detect_credential_change(h1, {"router": "x"})
    assert not changed

    changed, _ = detect_credential_change(h2, {"router": "y"})
    assert changed
