"""Lettura da OPNsense via API (solo GET): lease Kea DHCP e log delle query DNS di Unbound.

Endpoint verificati su OPNsense 26.7:
  /api/kea/leases4/search            MAC → IP, hostname
  /api/unbound/overview/searchQueries ultime 1000 query DNS con client e dominio
  /api/unbound/overview/totals/N     totali DNS e domini più bloccati
  /api/routes/gateway/status         stato della linea (latenza, perdita)
  /api/diagnostics/traffic/interface contatori byte delle interfacce
"""
import asyncio
import json
import ssl
import urllib.request
from base64 import b64encode

import truststore

from ..core.config import get_settings


def fetch(path: str, s=None, timeout: float = 20) -> dict:
    """GET sull'API di OPNsense; `s` permette di provare impostazioni non ancora salvate."""
    s = s or get_settings()
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
    data = await asyncio.to_thread(fetch, "kea/leases4/search?rowCount=2000&current=1")
    out = {}
    for r in data.get("rows", []):
        mac = (r.get("hwaddr") or "").lower()
        if mac and r.get("address"):
            out[mac] = (r["address"], (r.get("hostname") or "").strip() or None)
    return out


async def dns_queries() -> list[dict]:
    """Ultime query DNS (max 1000): {time, client, domain, action}."""
    data = await asyncio.to_thread(fetch, "unbound/overview/searchQueries?rowCount=1000&current=1")
    return [
        {"time": int(r["time"]), "client": r.get("client") or "", "domain": r.get("domain") or "",
         "action": r.get("action") or ""}
        for r in data.get("rows", []) if r.get("time") and r.get("domain")
    ]


async def dns_totals(top: int = 10) -> dict:
    """Totali DNS di Unbound: richieste, bloccate, domini più bloccati."""
    d = await asyncio.to_thread(fetch, f"unbound/overview/totals/{top}")
    return {
        "total": int(d.get("total") or 0),
        "blocked": int((d.get("blocked") or {}).get("total") or 0),
        "blocked_pct": float((d.get("blocked") or {}).get("pcnt") or 0),
        "since": int(d.get("start_time") or 0),
        "top_blocked": [
            {"domain": k.rstrip("."), "queries": int(v.get("total") or 0), "list": v.get("blocklist")}
            for k, v in (d.get("top_blocked") or {}).items()
        ],
    }


DOWN_STATES = ("down", "offline", "force_down")


async def gateways() -> list[dict]:
    d = await asyncio.to_thread(fetch, "routes/gateway/status")
    return [
        {"name": g.get("name"), "online": (g.get("status_translated") or "").lower() == "online",
         # "Latency"/"Packetloss" sono linea degradata, non caduta: per i disservizi conta solo offline
         "down": (g.get("status") or g.get("status_translated") or "").lower() in DOWN_STATES,
         "status": g.get("status_translated"), "delay": g.get("delay"), "loss": g.get("loss"),
         "monitor": g.get("monitor")}
        for g in d.get("items", [])
    ]


async def interface_bytes(name: str) -> tuple[int, int] | None:
    """(byte ricevuti, byte trasmessi) dell'interfaccia OPNsense `name` (es. "wan", "opt1")."""
    d = await asyncio.to_thread(fetch, "diagnostics/traffic/interface")
    i = (d.get("interfaces") or {}).get(name)
    if not i:
        return None
    return int(i.get("bytes received") or 0), int(i.get("bytes transmitted") or 0)


async def netflow_active() -> bool:
    d = await asyncio.to_thread(fetch, "diagnostics/netflow/status")
    return str(d.get("status") or "").lower() == "active"


async def bytes_per_address(since: int, until: int) -> dict[str, int]:
    """Byte per indirizzo sorgente da Insight (NetFlow con "Capture local").
    Formato di risposta da confermare sulla prima installazione con NetFlow attivo: parsing tollerante."""
    d = await asyncio.to_thread(
        fetch, f"diagnostics/networkinsight/top/FlowSourceAddrTotals/{since}/{until}/src_addr/octets/%20/200"
    )
    rows = d if isinstance(d, list) else (d.get("rows") or d.get("items") or [])
    out: dict[str, int] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        addr = r.get("src_addr") or r.get("key")
        total = r.get("total") or r.get("octets") or 0
        if addr:
            out[str(addr)] = out.get(str(addr), 0) + int(float(total))
    return out
