"""Security validation utilities for upstream provider URLs and network calls.
Guarantees SSRF protection:
- HTTPS only (unless ALLOW_LOCAL_UPSTREAMS=true)
- Blocks private, loopback, link-local, and reserved IP ranges (both literals and DNS resolution)
- Disallows cross-host redirects
"""
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse
import httpx
from app.config import settings

def is_ip_blocked(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if IP address is in a private, loopback, link-local, or reserved range."""
    return (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    )

def validate_base_url(url: str, allow_local: Optional[bool] = None) -> str:
    """
    Validate upstream provider base_url against SSRF and protocol restrictions.
    Returns stripped normalized base URL without trailing slash.
    """
    if allow_local is None:
        allow_local = settings.ALLOW_LOCAL_UPSTREAMS

    if not url or not url.strip():
        raise ValueError("Provider base_url cannot be empty")

    url = url.strip()
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL format: '{url}'")

    if not allow_local:
        if parsed.scheme.lower() != "https":
            raise ValueError(f"Invalid protocol '{parsed.scheme}': Upstream provider URLs must use HTTPS.")
    else:
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"Invalid protocol '{parsed.scheme}': Must use HTTP or HTTPS.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Could not extract hostname from URL '{url}'")

    if not allow_local:
        # Check if direct IP address
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if is_ip_blocked(ip_obj):
                raise ValueError(f"Direct IP '{hostname}' belongs to a blocked private or loopback range.")
        except ValueError as e:
            # If "belongs to a blocked" in str(e), re-raise
            if "belongs to a blocked" in str(e):
                raise
            # Not an IP literal, resolve DNS
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for entry in addr_info:
                    resolved_ip_str = entry[4][0]
                    resolved_ip = ipaddress.ip_address(resolved_ip_str)
                    if is_ip_blocked(resolved_ip):
                        raise ValueError(
                            f"Hostname '{hostname}' resolves to private/loopback/link-local IP {resolved_ip_str}."
                        )
            except socket.gaierror as dns_err:
                raise ValueError(f"DNS resolution failed for host '{hostname}': {dns_err}") from dns_err

    # Normalize: strip trailing slash
    return url.rstrip("/")

async def safe_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs
) -> httpx.Response:
    """
    Execute HTTP request ensuring redirects to different hosts are strictly blocked.
    """
    parsed_initial = urlparse(url)
    # Ensure redirect following is controlled
    kwargs["follow_redirects"] = False
    
    current_url = url
    current_method = method
    max_redirects = 5
    redirect_count = 0

    while True:
        resp = await client.request(current_method, current_url, **kwargs)
        if resp.is_redirect and "location" in resp.headers:
            redirect_count += 1
            if redirect_count > max_redirects:
                raise ValueError("Too many redirects")
            
            target_url = resp.headers["location"]
            # Parse target url
            parsed_target = urlparse(target_url)
            # If relative URL, it stays on the same host
            if parsed_target.netloc:
                if parsed_target.netloc.lower() != parsed_initial.netloc.lower():
                    raise ValueError(f"Cross-host redirect blocked: from {parsed_initial.netloc} to {parsed_target.netloc}")
            
            current_url = target_url
            if resp.status_code in (301, 302, 303):
                current_method = "GET"
                kwargs.pop("json", None)
                kwargs.pop("data", None)
            continue
        return resp
