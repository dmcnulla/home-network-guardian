from __future__ import annotations

import ipaddress
import json
import logging
import re
import shlex
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAC_REGEX = re.compile(r"([0-9a-f]{1,2}(?::[0-9a-f]{1,2}){5})", re.IGNORECASE)
IP_REGEX = re.compile(r"\(([^)]+)\)")
IPV6_REGEX = re.compile(
    r"([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}", re.IGNORECASE
)


@dataclass(slots=True)
class ObservedDevice:
    mac: str
    ip: str | None
    vendor: str | None = None


def normalize_mac(mac: str) -> str:
    parts = [p.zfill(2) for p in mac.lower().split(":")]
    return ":".join(parts)


# MAC vendor cache
_mac_vendor_cache: dict[str, str | None] = {}
_cache_file = Path.home() / ".cache" / "hng" / "mac_vendors.json"


def load_mac_cache() -> None:
    """Load MAC vendor cache from disk."""
    global _mac_vendor_cache
    try:
        if _cache_file.exists():
            with open(_cache_file) as f:
                _mac_vendor_cache = json.load(f)
            logger.debug("Loaded %d MAC vendors from cache", len(_mac_vendor_cache))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to load MAC cache: %s", exc)


def save_mac_cache() -> None:
    """Save MAC vendor cache to disk."""
    try:
        _cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(_cache_file, "w") as f:
            json.dump(_mac_vendor_cache, f, indent=2)
        logger.debug("Saved %d MAC vendors to cache", len(_mac_vendor_cache))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to save MAC cache: %s", exc)


def lookup_mac_vendor(mac: str) -> str | None:
    """
    Lookup MAC address vendor/manufacturer using online services.
    
    Uses caching to minimize API calls.
    """
    # Check cache first
    if mac in _mac_vendor_cache:
        return _mac_vendor_cache[mac]
    
    vendor = None
    
    # Try maclookup.app API
    try:
        import requests
        
        # Format MAC for API (remove colons)
        mac_clean = mac.replace(":", "")
        
        response = requests.get(
            f"https://api.maclookup.app/v2/macs/{mac_clean}",
            timeout=3,
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("company"):
                vendor = data["company"]
                logger.debug("MAC %s -> %s (maclookup.app)", mac, vendor)
    except Exception as exc:  # noqa: BLE001
        logger.debug("maclookup.app failed for %s: %s", mac, exc)
    
    # Try macvendors.com as fallback (free API, no key needed)
    if not vendor:
        try:
            import requests
            
            response = requests.get(
                f"https://api.macvendors.com/{mac}",
                timeout=3,
            )
            
            if response.status_code == 200:
                vendor = response.text.strip()
                if vendor and not vendor.startswith("Error"):
                    logger.debug("MAC %s -> %s (macvendors.com)", mac, vendor)
                else:
                    vendor = None
        except Exception as exc:  # noqa: BLE001
            logger.debug("macvendors.com failed for %s: %s", mac, exc)
    
    # Cache result (even if None to avoid repeated lookups)
    _mac_vendor_cache[mac] = vendor
    
    return vendor


def enrich_devices_with_vendors(
    devices: list[ObservedDevice], max_workers: int = 5
) -> None:
    """
    Enrich device list with vendor information using MAC lookups.
    
    Modifies devices in place. Uses threading to speed up lookups.
    """
    load_mac_cache()
    
    # Only lookup devices that don't have vendor info yet
    devices_to_lookup = [d for d in devices if not d.vendor]
    
    if not devices_to_lookup:
        return
    
    logger.info("Looking up vendors for %d devices...", len(devices_to_lookup))
    
    def lookup_and_set(device: ObservedDevice) -> None:
        # Skip broadcast/multicast MACs
        if device.mac.startswith(("ff:ff:ff", "01:00:5e", "33:33:")):
            return
        vendor = lookup_mac_vendor(device.mac)
        if vendor:
            device.vendor = vendor
    
    # Use ThreadPoolExecutor for parallel lookups (but limited concurrency)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(lookup_and_set, device)
            for device in devices_to_lookup
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Vendor lookup failed: %s", exc)
    
    save_mac_cache()
    
    enriched = sum(1 for d in devices if d.vendor)
    logger.info("Enriched %d/%d devices with vendor info", enriched, len(devices))


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


def get_local_networks() -> list[str]:
    """Detect all local network subnets on active interfaces."""
    networks: list[str] = []
    
    try:
        # Parse ifconfig to get all interface IPs and netmasks
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        
        if result.returncode != 0:
            return networks
        
        current_iface = None
        ip_addr = None
        netmask = None
        
        for line in result.stdout.splitlines():
            line = line.rstrip()
            
            # New interface
            if line and not line.startswith(("\t", " ")):
                # Process previous interface if we have complete info
                if ip_addr and netmask and current_iface:
                    try:
                        # Calculate network from IP and netmask
                        iface_obj = ipaddress.IPv4Interface(
                            f"{ip_addr}/{netmask}"
                        )
                        network = str(iface_obj.network)
                        if network not in networks:
                            # Skip loopback
                            if not iface_obj.network.is_loopback:
                                networks.append(network)
                                logger.debug(
                                    "Found network %s on %s",
                                    network,
                                    current_iface,
                                )
                    except ValueError:
                        pass
                
                current_iface = line.split(":")[0]
                ip_addr = None
                netmask = None
            
            # Look for IPv4 address and netmask
            if "inet " in line and "127.0.0.1" not in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "inet" and i + 1 < len(parts):
                        ip_addr = parts[i + 1]
                    elif part == "netmask" and i + 1 < len(parts):
                        # netmask might be in hex (0xffffff00)
                        mask_str = parts[i + 1]
                        if mask_str.startswith("0x"):
                            # Convert hex to dotted decimal
                            mask_int = int(mask_str, 16)
                            netmask = socket.inet_ntoa(
                                mask_int.to_bytes(4, "big")
                            )
                        else:
                            netmask = mask_str
        
        # Process last interface
        if ip_addr and netmask and current_iface:
            try:
                iface_obj = ipaddress.IPv4Interface(f"{ip_addr}/{netmask}")
                network = str(iface_obj.network)
                if network not in networks:
                    if not iface_obj.network.is_loopback:
                        networks.append(network)
                        logger.debug(
                            "Found network %s on %s", network, current_iface
                        )
            except ValueError:
                pass
                        
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not determine local networks: %s", exc)
    
    return networks


def get_local_network() -> str | None:
    """Detect the local network subnet (e.g., 192.168.1.0/24)."""
    networks = get_local_networks()
    return networks[0] if networks else None


def ping_host(ip: str) -> bool:
    """Ping a single host to populate ARP cache."""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True,
            timeout=2,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):  # noqa: BLE001
        return False


def active_network_scan(
    network: str | None = None, max_workers: int = 50
) -> None:
    """
    Perform an active network scan by pinging all hosts in the subnet(s).
    This populates the ARP cache with all responding devices.
    """
    networks_to_scan: list[str] = []
    
    if network:
        networks_to_scan = [network]
    else:
        networks_to_scan = get_local_networks()
    
    if not networks_to_scan:
        logger.warning("Could not determine local network for active scan")
        return

    for net_str in networks_to_scan:
        try:
            net = ipaddress.IPv4Network(net_str)
            
            # Skip very large networks (more than /16)
            if net.num_addresses > 65536:
                logger.warning("Skipping large network %s", net_str)
                continue
            
            hosts = [str(ip) for ip in net.hosts()]
            
            logger.info(
                "Starting active scan of %d hosts in %s", len(hosts), net_str
            )
            
            alive_count = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(ping_host, host): host for host in hosts
                }
                for future in as_completed(futures):
                    if future.result():
                        alive_count += 1
            
            logger.info(
                "Active scan complete: %d hosts responded in %s",
                alive_count,
                net_str,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Active scan failed for %s: %s", net_str, exc)


def discover_bonjour() -> list[ObservedDevice]:
    """Discover devices via Bonjour/mDNS (dns-sd)."""
    devices: list[ObservedDevice] = []
    try:
        # Browse for common service types
        services = ["_http._tcp", "_ssh._tcp", "_smb._tcp", "_airplay._tcp"]
        
        for service in services:
            try:
                result = subprocess.run(
                    ["dns-sd", "-B", service, "local.", "-t", "1"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                if result.returncode == 0:
                    logger.debug("Found Bonjour devices on %s", service)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        # Also check arp cache populated by mDNS
        try:
            result = subprocess.run(
                ["arp", "-an"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if ".local" in line.lower() or "224.0.0.251" in line:
                        devices.extend(parse_arp_output(line))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
    except Exception as exc:  # noqa: BLE001
        logger.debug("Bonjour discovery failed: %s", exc)
    
    logger.info("Bonjour discovery found %d devices", len(devices))
    return devices


def discover_upnp() -> list[ObservedDevice]:
    """Discover devices via UPnP/SSDP."""
    devices: list[ObservedDevice] = []
    
    try:
        # SSDP multicast discovery
        ssdp_request = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 2\r\n"
            "ST: ssdp:all\r\n"
            "\r\n"
        )
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.sendto(ssdp_request.encode(), ("239.255.255.250", 1900))
        
        found_ips = set()
        try:
            while True:
                data, addr = sock.recvfrom(4096)
                if addr[0] not in found_ips:
                    found_ips.add(addr[0])
                    # Trigger ARP lookup
                    ping_host(addr[0])
        except socket.timeout:
            pass
        finally:
            sock.close()
        
        # Query ARP for UPnP devices we found
        if found_ips:
            result = subprocess.run(
                ["arp", "-an"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                for ip in found_ips:
                    for line in result.stdout.splitlines():
                        if ip in line:
                            devices.extend(parse_arp_output(line))
                            
    except Exception as exc:  # noqa: BLE001
        logger.debug("UPnP discovery failed: %s", exc)
    
    logger.info("UPnP discovery found %d devices", len(devices))
    return devices


def discover_ipv6_neighbors() -> list[ObservedDevice]:
    """Discover devices via IPv6 neighbor discovery."""
    devices: list[ObservedDevice] = []
    
    try:
        result = subprocess.run(
            ["ndp", "-an"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                # IPv6 neighbor table format similar to ARP
                mac_match = MAC_REGEX.search(line)
                ipv6_match = IPV6_REGEX.search(line)
                
                if mac_match:
                    mac = normalize_mac(mac_match.group(0))
                    ip = ipv6_match.group(0) if ipv6_match else None
                    devices.append(ObservedDevice(mac=mac, ip=ip))
                    
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.debug("IPv6 neighbor discovery not available")
    except Exception as exc:  # noqa: BLE001
        logger.debug("IPv6 discovery failed: %s", exc)
    
    logger.info("IPv6 discovery found %d devices", len(devices))
    return devices


def get_local_device() -> ObservedDevice | None:
    """Get MAC and IP of the local device."""
    try:
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Get MAC from ifconfig
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        
        if result.returncode == 0:
            current_interface = None
            for line in result.stdout.splitlines():
                # Track which interface we're looking at
                if not line.startswith(("\t", " ")):
                    current_interface = line.split(":")[0]
                
                # Look for our IP address
                if local_ip in line and current_interface:
                    # Now find the MAC for this interface
                    for search_line in result.stdout.splitlines():
                        if current_interface in search_line:
                            mac_match = MAC_REGEX.search(search_line)
                            if mac_match:
                                mac = normalize_mac(mac_match.group(0))
                                logger.info(
                                    "Local device: %s (%s)", mac, local_ip
                                )
                                return ObservedDevice(mac=mac, ip=local_ip)
                    
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to get local device: %s", exc)
    
    return None


def deduplicate_devices(
    devices: list[ObservedDevice],
) -> list[ObservedDevice]:
    """Remove duplicate devices, preferring entries with IP addresses."""
    seen: dict[str, ObservedDevice] = {}
    
    for device in devices:
        if device.mac in seen:
            # Prefer device with IP address
            if device.ip and not seen[device.mac].ip:
                seen[device.mac] = device
        else:
            seen[device.mac] = device
    
    return list(seen.values())


def discover_devices(
    arp_command: str,
    active_scan: bool = True,
    lookup_vendors: bool = False,
) -> list[ObservedDevice]:
    """
    Discover devices on the network using multiple methods.
    
    Args:
        arp_command: Command to query ARP table
        active_scan: If True, perform active network scan first to
            populate ARP cache
        lookup_vendors: If True, lookup MAC vendor information online
    
    Returns:
        List of observed devices with MAC addresses and IPs
    """
    all_devices: list[ObservedDevice] = []
    
    # Method 1: Include local device
    local_device = get_local_device()
    if local_device:
        all_devices.append(local_device)
    
    # Method 2: Active network scan (ping sweep)
    if active_scan:
        active_network_scan()
    
    # Method 3: Query ARP table
    cmd = shlex.split(arp_command)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=10
        )
        if result.returncode == 0:
            all_devices.extend(parse_arp_output(result.stdout))
    except FileNotFoundError:
        logger.warning("ARP command not found: %s", arp_command)
    except subprocess.TimeoutExpired:
        logger.error("ARP command timed out")
    
    # Method 4: Bonjour/mDNS discovery
    all_devices.extend(discover_bonjour())
    
    # Method 5: UPnP/SSDP discovery
    all_devices.extend(discover_upnp())
    
    # Method 6: IPv6 neighbor discovery
    all_devices.extend(discover_ipv6_neighbors())
    
    # Deduplicate devices by MAC address
    unique_devices = deduplicate_devices(all_devices)
    
    logger.info(
        "Total discovered: %d devices (%d after deduplication)",
        len(all_devices),
        len(unique_devices),
    )
    
    # Enrich with vendor information if requested
    if lookup_vendors:
        enrich_devices_with_vendors(unique_devices)
    
    return unique_devices
