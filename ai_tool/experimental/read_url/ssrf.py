from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from ai_tool.experimental.read_url.config import ALLOWED_SCHEMES, BLOCKED_HOSTNAMES

_IPV4_LITERAL = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d?\d)){3})$"
)
_IPV6_LITERAL = re.compile(r"^\[([0-9a-fA-F:]+)\]$")


def _normalize_host(hostname: str) -> str:
    host = hostname.strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        return host[1:-1].lower()
    return host


def _parse_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        if _IPV4_LITERAL.match(host):
            return ipaddress.ip_address(host)
        if host.startswith("[") and host.endswith("]"):
            return ipaddress.ip_address(host[1:-1])
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_blocked_hostname(hostname: str) -> bool:
    host = _normalize_host(hostname)
    if host in BLOCKED_HOSTNAMES:
        return True
    if host.endswith(".localhost"):
        return True
    if host == "0.0.0.0":
        return True
    return False


def resolve_public_ips(hostname: str, port: int) -> tuple[list[str], str | None]:
    """Resolve hostname; return IPs if all public, else error message."""
    host = _normalize_host(hostname)
    ip_literal = _parse_ip(host)
    if ip_literal is not None:
        if is_blocked_ip(ip_literal):
            return [], "ssrf blocked: private or loopback IP"
        return [str(ip_literal)], None
    if is_blocked_hostname(host):
        return [], "ssrf blocked: hostname not allowed"
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return [], f"connection failure: {exc}"
    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return [], f"ssrf blocked: invalid resolved IP {ip_str!r}"
        if is_blocked_ip(ip):
            return [], "ssrf blocked: DNS resolved to private or loopback address"
        if ip_str not in ips:
            ips.append(ip_str)
    if not ips:
        return [], "connection failure: no addresses resolved"
    return ips, None


def validate_url(url: str) -> tuple[str | None, str | None]:
    """
    Validate URL for fetch. Returns (normalized_url, error).
    """
    raw = (url or "").strip()
    if not raw:
        return None, "malformed url: empty"
    parsed = urlparse(raw)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return None, f"unsupported scheme: {parsed.scheme or '(none)'}"
    if not parsed.netloc:
        return None, "malformed url: missing host"
    if parsed.username or parsed.password:
        return None, "malformed url: userinfo not allowed"
    hostname = parsed.hostname
    if not hostname:
        return None, "malformed url: missing hostname"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    _, err = resolve_public_ips(hostname, port)
    if err:
        return None, err
    return raw, None
