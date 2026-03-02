from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass

MAC_REGEX = re.compile(r"([0-9a-f]{1,2}(?::[0-9a-f]{1,2}){5})", re.IGNORECASE)
IP_REGEX = re.compile(r"\(([^)]+)\)")


@dataclass(slots=True)
class ObservedDevice:
    mac: str
    ip: str | None


def normalize_mac(mac: str) -> str:
    parts = [p.zfill(2) for p in mac.lower().split(":")]
    return ":".join(parts)


def parse_arp_output(output: str) -> list[ObservedDevice]:
    devices: list[ObservedDevice] = []
    for line in output.splitlines():
        mac_match = MAC_REGEX.search(line)
        if not mac_match:
            continue
        ip_match = IP_REGEX.search(line)
        mac = normalize_mac(mac_match.group(1))
        ip = ip_match.group(1) if ip_match else None
        devices.append(ObservedDevice(mac=mac, ip=ip))
    return devices


def discover_devices(arp_command: str) -> list[ObservedDevice]:
    cmd = shlex.split(arp_command)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []
    return parse_arp_output(result.stdout)
