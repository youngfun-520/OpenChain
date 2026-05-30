"""Web search and fetch tools."""
import httpx
from duckduckgo_search import DDGS
from openchain.tools.base import Tool
from openchain.security import SecurityError
from typing import Set


# Blocked hostnames and IP ranges for SSRF protection
BLOCKED_HOSTS: Set[str] = {
    "localhost",
    "127.0.0.1",
    "::1",
    "metadata.google.internal",
    "metadata.internal",
}

# Blocked IP ranges (CIDR notation)
BLOCKED_IP_RANGES = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",  # AWS metadata
    "100.64.0.0/10",
    "fc00::/7",
    "fe80::/10",
]


def _is_blocked_url(url: str) -> tuple[bool, str]:
    """Check if URL is blocked for SSRF reasons.

    Returns (is_blocked, reason).
    """
    from urllib.parse import urlparse
    import ipaddress

    parsed = urlparse(url)

    # Only allow http/https
    if parsed.scheme not in ("http", "https"):
        return True, f"Unsupported scheme: {parsed.scheme}"

    host = parsed.hostname
    if not host:
        return True, "No hostname in URL"

    # Check blocked hosts
    if host.lower() in BLOCKED_HOSTS:
        return True, f"Blocked host: {host}"

    # Check if host resolves to blocked IP
    try:
        # Check if it's already an IP address
        ip = ipaddress.ip_address(host)
        for cidr in BLOCKED_IP_RANGES:
            if ip in ipaddress.ip_network(cidr):
                return True, f"Blocked IP range: {cidr}"
        return False, ""
    except ValueError:
        # Not an IP address, try to resolve it
        try:
            import socket
            addrs = socket.getaddrinfo(host, None)
            for family, type_, proto, canonname, sockaddr in addrs:
                addr = sockaddr[0]
                try:
                    ip = ipaddress.ip_address(addr)
                    for cidr in BLOCKED_IP_RANGES:
                        if ip in ipaddress.ip_network(cidr):
                            return True, f"Blocked IP range: {cidr} (resolved from {host})"
                except ValueError:
                    continue
        except Exception:
            pass  # If resolution fails, let it proceed (will fail at fetch time)

    return False, ""


class WebSearchTool(Tool):
    def __init__(self):
        super().__init__("web_search", "Search the web")

    async def execute(self, query: str, num_results: int = 5, **kwargs) -> dict:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
            return {
                "status": "success",
                "results": [
                    {"title": r["title"], "url": r["href"], "body": r["body"]}
                    for r in results
                ]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WebFetchTool(Tool):
    def __init__(self):
        super().__init__("web_fetch", "Fetch web page content")

    async def execute(self, url: str, **kwargs) -> dict:
        # SSRF check
        blocked, reason = _is_blocked_url(url)
        if blocked:
            return {"status": "error", "message": f"SSRF blocked: {reason}"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                return {
                    "status": "success",
                    "content": response.text[:10000],
                    "url": url,
                    "status_code": response.status_code
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}