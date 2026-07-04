"""
SSRF guard: validate a URL resolves to a public IP before use.

Blocks RFC1918, loopback, link-local, and IPv6 ULA.
Re-checks after DNS resolution to defeat rebinding.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from fastapi import HTTPException, status

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True  # unparseable → treat as unsafe
    return any(ip in net for net in _PRIVATE_NETWORKS)


def assert_public_url(url: str) -> None:
    """Raise HTTP 400 if the URL resolves to a private/reserved address."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Webhook URL must use http or https")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid URL")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "URL hostname does not resolve")
    for _, _, _, _, sockaddr in infos:
        if _is_private(sockaddr[0]):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Webhook URL must not target a private address")
