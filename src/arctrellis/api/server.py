"""Loopback-only server construction.

Binding is validated here and nowhere else. There is deliberately no option to
widen it: create_server raises for any host that is not an IPv4/IPv6 loopback
address or the literal name localhost, so a misconfiguration cannot turn a
read-only local interface into a network service (D-148).
"""

from __future__ import annotations

import ipaddress
from http.server import ThreadingHTTPServer
from typing import Any

from .app import ApiApplication, make_handler
from .service import API_PREFIX, AnalysisService

#: Hosts accepted by create_server. Anything else is refused.
ALLOWED_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8756


class UnsafeBindError(ValueError):
    """The requested bind address is not a loopback address."""


def is_loopback(host: str) -> bool:
    """Whether a bind address is loopback-only.

    ``localhost`` is accepted by name. Any other name is refused rather than
    resolved, because resolving it would perform a network lookup and a hostname
    can point anywhere.
    """
    if not isinstance(host, str) or not host:
        return False
    candidate = host.strip()
    if candidate.casefold() in ALLOWED_HOSTS:
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


class QuietHTTPServer(ThreadingHTTPServer):
    """A loopback server that does not print client-disconnect noise.

    Refusing an oversized body leaves unread bytes on the socket, so a client that
    already sent them may reset the connection. That is ordinary client behaviour,
    not a server fault, and it must not print a traceback into the console of a
    process that may be something other than this service.
    """

    daemon_threads = True

    def handle_error(self, request: object, client_address: object) -> None:
        return None


def create_server(
    root: str,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    service: AnalysisService | None = None,
    max_source_bytes: int | None = None,
) -> QuietHTTPServer:
    """Analyze the configured root once and return a loopback-only server.

    ``root`` is fixed here and is unreachable from any request. The returned server
    is not started; the caller owns ``serve_forever`` and ``shutdown``.
    """
    if not is_loopback(host):
        raise UnsafeBindError(
            f"refusing to bind {host!r}: this service is loopback-only. "
            "It has no authentication and must never be exposed to a network."
        )
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    analysis = service or AnalysisService.from_root(root, max_source_bytes=max_source_bytes)
    application = ApiApplication(analysis)
    address = "::1" if host.strip().casefold() in ("::1", "localhost") else host
    return QuietHTTPServer((address, port), make_handler(application))


def server_banner(server: ThreadingHTTPServer) -> dict[str, Any]:
    """Describe the running listener without disclosing the analyzed root."""
    host, port = server.server_address[0], server.server_address[1]
    return {
        "host": host,
        "port": port,
        "loopback_only": is_loopback(str(host)),
        "api_prefix": API_PREFIX,
    }
