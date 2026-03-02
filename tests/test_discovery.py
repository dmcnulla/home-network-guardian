from home_network_guardian.discovery import parse_arp_output


def test_parse_arp_output_extracts_mac_and_ip() -> None:
    out = "? (192.168.1.10) at aa:bb:cc:dd:ee:ff on en0 ifscope [ethernet]"
    items = parse_arp_output(out)
    assert len(items) == 1
    assert items[0].mac == "aa:bb:cc:dd:ee:ff"
    assert items[0].ip == "192.168.1.10"
