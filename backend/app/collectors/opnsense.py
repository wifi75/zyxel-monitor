"""Lettura da OPNsense via API (solo GET): lease Kea DHCP e log delle query DNS di Unbound.

Endpoint verificati su OPNsense 26.7:
  /api/kea/leases4/search            MAC → IP, hostname
  /api/unbound/overview/searchQueries ultime 1000 query DNS con client e dominio
"""
import asyncio
import json
import ssl
import urllib.request
from base64 import b64encode

import truststore

from ..core.config import get_settings


def _get(path: str, timeout: float = 20) -> dict:
    s = get_settings()
    req = urllib.request.Request(f"{s.opnsense_url.rstrip('/')}/api/{path}")
    token = b64encode(f"{s.opnsense_key}:{s.opnsense_secret}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)   # certificati del sistema operativo
    if not s.opnsense_verify_tls:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.load(resp)


def enabled() -> bool:
    s = get_settings()
    return bool(s.opnsense_url and s.opnsense_key and s.opnsense_secret)


async def leases() -> dict[str, tuple[str, str | None]]:
    """{mac: (ip, hostname)} dai lease Kea DHCPv4."""
    data = await asyncio.to_thread(_get, "kea/leases4/search?rowCount=2000&current=1")
    out = {}
    for r in data.get("rows", []):
        mac = (r.get("hwaddr") or "").lower()
        if mac and r.get("address"):
            out[mac] = (r["address"], (r.get("hostname") or "").strip() or None)
    return out


async def dns_queries() -> list[dict]:
    """Ultime query DNS (max 1000): {time, client, domain, action}."""
    data = await asyncio.to_thread(_get, "unbound/overview/searchQueries?rowCount=1000&current=1")
    return [
        {"time": int(r["time"]), "client": r.get("client") or "", "domain": r.get("domain") or "",
         "action": r.get("action") or ""}
        for r in data.get("rows", []) if r.get("time") and r.get("domain")
    ]
