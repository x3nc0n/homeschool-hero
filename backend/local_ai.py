from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_RFC1918_NETWORKS = (
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
)
_IPV6_LOCAL_NETWORKS = (ipaddress.ip_network('fc00::/7'),)


def _is_local_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if address.is_loopback:
        return True
    networks = _RFC1918_NETWORKS if address.version == 4 else _IPV6_LOCAL_NETWORKS
    return any(address in network for network in networks)


def validate_local_ollama_host(host: str) -> None:
    parsed = urlsplit((host or '').strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise ValueError('OLLAMA_HOST must be an HTTP(S) URL with a local hostname when AI_LOCAL_ONLY=true.')
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError('OLLAMA_HOST must contain a valid port when AI_LOCAL_ONLY=true.') from exc

    hostname = parsed.hostname.rstrip('.').lower()
    if hostname == 'localhost':
        return

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            resolved = {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(hostname, parsed.port, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as exc:
            raise ValueError(
                'OLLAMA_HOST must resolve only to localhost or a private network when AI_LOCAL_ONLY=true.'
            ) from exc
        if not resolved:
            raise ValueError(
                'OLLAMA_HOST must resolve only to localhost or a private network when AI_LOCAL_ONLY=true.'
            )
        addresses = resolved
    else:
        addresses = {address}

    if not all(_is_local_address(item) for item in addresses):
        raise ValueError(
            'OLLAMA_HOST must resolve only to localhost or a private network when AI_LOCAL_ONLY=true.'
        )
