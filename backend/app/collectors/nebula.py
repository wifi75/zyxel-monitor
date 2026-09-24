"""Nebula OpenAPI (richiede la licenza Pro): https://zyxelnetworks.github.io/NebulaOpenAPI/

Endpoint usati (dalla specifica ufficiale 3.1.0):
  GET  /v1/nebula/organizations                         org con modalità (PRO, BASE, …)
  GET  /v1/nebula/organizations/{orgId}/sites           siti
  GET  /v1/nebula/organizations/{orgId}/sites/devices   dispositivi per sito
  GET  /v1/nebula/{siteId}/firmware-status              versione attuale e più recente
  GET  /v1/nebula/{siteId}/online-status                ONLINE / OFFLINE
  GET  /v1/nebula/{siteId}/ap/wlan-settings             SSID (PATCH per modificarli)
  GET  /v1/nebula/{siteId}/ap/wlan-band-mode            bande per SSID (PATCH per modificarle)
  POST /v1/nebula/{siteId}/livetool/{devId}/reboot      riavvio
Potenza radio e canali non sono esposti dall'API.
"""
import asyncio
import json
import ssl
import urllib.error
import urllib.request

import truststore

BASE = "https://api.nebula.zyxel.com"


class NebulaError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _call(key: str, method: str, path: str, body=None, timeout: float = 20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("X-ZyxelNebula-API-Key", key)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        if exc.code == 401:
            raise NebulaError(401, "Chiave API non valida o revocata") from None
        if exc.code == 403:
            raise NebulaError(403, "Funzione riservata alla licenza Nebula Pro") from None
        raise NebulaError(exc.code, f"Nebula ha risposto {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise NebulaError(0, f"Nebula non raggiungibile: {exc.reason}") from None
    return json.loads(raw) if raw else None


async def call(key: str, method: str, path: str, body=None):
    return await asyncio.to_thread(_call, key, method, path, body)


async def discover(key: str) -> dict:
    """Organizzazioni con modalità di licenza e, dove l'API lo permette, i loro siti."""
    orgs = await call(key, "GET", "/v1/nebula/organizations") or []
    out = []
    for o in orgs:
        item = {"orgId": o["orgId"], "name": o["name"], "mode": o.get("mode"), "sites": [], "error": None}
        try:
            sites = await call(key, "GET", f"/v1/nebula/organizations/{o['orgId']}/sites") or []
            item["sites"] = [s for s in sites if s]
        except NebulaError as exc:
            item["error"] = str(exc)
        out.append(item)
    return {"organizations": out}


async def devices(key: str, org_id: str, site_id: str) -> list[dict]:
    """Dispositivi del sito con stato online e firmware."""
    per_site, fw, online = await asyncio.gather(
        call(key, "GET", f"/v1/nebula/organizations/{org_id}/sites/devices"),
        call(key, "GET", f"/v1/nebula/{site_id}/firmware-status"),
        call(key, "GET", f"/v1/nebula/{site_id}/online-status"),
    )
    devs = next((s["devices"] for s in per_site or [] if s and s.get("siteId") == site_id), [])
    fw_by = {f["devId"]: f for f in fw or []}
    on_by = {o["devId"]: o["currentStatus"] for o in online or []}
    rows = []
    for d in devs:
        if not d:
            continue
        f = fw_by.get(d["devId"], {})
        rows.append({
            "devId": d["devId"], "name": d.get("name"), "model": d.get("model"), "mac": (d.get("mac") or "").lower(),
            "type": d.get("type"), "online": on_by.get(d["devId"]) == "ONLINE",
            "currentVersion": f.get("currentVersion"), "latestVersion": f.get("latestVersion"),
            "firmwareStatus": f.get("status"), "lastUpgradeTime": f.get("lastUpgradeTime"),
        })
    return sorted(rows, key=lambda r: (r["name"] or "").lower())


async def ssids(key: str, site_id: str) -> list[dict]:
    """SSID del sito: l'API non dà un id, si assume che l'ordine corrisponda agli slot 1..8 di Nebula."""
    settings, bands = await asyncio.gather(
        call(key, "GET", f"/v1/nebula/{site_id}/ap/wlan-settings"),
        call(key, "GET", f"/v1/nebula/{site_id}/ap/wlan-band-mode"),
    )
    band_by = {b["ssid"]: b.get("enabledBands") or [] for b in bands or []}
    return [{**s, "id": i, "enabledBands": band_by.get(i, [])} for i, s in enumerate(settings or [], start=1)]
