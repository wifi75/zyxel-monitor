"""Integrazione Nebula (licenza Pro): collegamento, firmware e stato, SSID, riavvio."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .collectors import nebula
from .collectors.nebula import NebulaError
from .core import store
from .core.config import get_settings
from .core.security import current_user

router = APIRouter(prefix="/api/nebula", dependencies=[Depends(current_user)])


def _cfg() -> tuple[str, str, str]:
    s = get_settings()
    if not (s.nebula_api_key and s.nebula_org_id and s.nebula_site_id):
        raise HTTPException(409, "Nebula non collegato: configuralo in Impostazioni")
    return s.nebula_api_key, s.nebula_org_id, s.nebula_site_id


def _fail(exc: NebulaError):
    raise HTTPException(502 if exc.status in (0, 500, 502, 503) else 400, str(exc))


class DiscoverIn(BaseModel):
    api_key: str = ""     # vuoto = quella salvata


@router.post("/discover")
async def discover(body: DiscoverIn):
    key = body.api_key.strip() or get_settings().nebula_api_key
    if not key:
        return {"ok": False, "message": "Incolla la chiave API di Nebula."}
    try:
        data = await nebula.discover(key)
    except NebulaError as exc:
        return {"ok": False, "message": str(exc)}
    pro = any(o["mode"] in ("PRO", "TRIAL") for o in data["organizations"])
    return {"ok": True, "pro": pro, **data,
            "message": None if pro else "La chiave funziona, ma nessuna organizzazione ha la licenza Pro: "
                                        "firmware, SSID e riavvio non saranno disponibili."}


class ConnectIn(BaseModel):
    api_key: str = ""
    org_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)


@router.put("/connect")
def connect(body: ConnectIn):
    values = {"nebula_org_id": body.org_id, "nebula_site_id": body.site_id}
    if body.api_key.strip():
        values["nebula_api_key"] = body.api_key.strip()
    store.set_settings(values)
    return status()


@router.delete("/connect")
def disconnect():
    store.set_settings({"nebula_api_key": "", "nebula_org_id": "", "nebula_site_id": ""})
    return status()


@router.get("/status")
def status():
    s = get_settings()
    return {"configured": bool(s.nebula_api_key and s.nebula_org_id and s.nebula_site_id),
            "has_key": bool(s.nebula_api_key), "org_id": s.nebula_org_id, "site_id": s.nebula_site_id}


@router.get("/devices")
async def devices():
    key, org, site = _cfg()
    try:
        rows = await nebula.devices(key, org, site)
    except NebulaError as exc:
        _fail(exc)
    return {"devices": rows, "updates": sum(r["firmwareStatus"] == "NOT_UP_TO_DATE" for r in rows)}


@router.post("/devices/{dev_id}/reboot")
async def reboot(dev_id: str):
    key, _, site = _cfg()
    try:
        return await nebula.call(key, "POST", f"/v1/nebula/{site}/livetool/{dev_id}/reboot")
    except NebulaError as exc:
        _fail(exc)


@router.get("/ssids")
async def list_ssids():
    key, _, site = _cfg()
    try:
        rows = await nebula.ssids(key, site)
    except NebulaError as exc:
        _fail(exc)
    for r in rows:   # la password della rete non esce dal server
        r["has_wpa_key"] = bool(r.pop("wpaKey", None))
    return rows


class SsidIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=32)
    enabled: bool | None = None
    bands: list[str] | None = None     # es. ["2.4G", "5G"], valori come li restituisce Nebula


@router.patch("/ssids/{ssid_id}")
async def update_ssid(ssid_id: int, body: SsidIn):
    key, _, site = _cfg()
    try:
        current = next((s for s in await nebula.ssids(key, site) if s["id"] == ssid_id), None)
        if not current:
            raise HTTPException(404, "Rete Wi-Fi non trovata")
        if body.name is not None or body.enabled is not None:
            # l'API vuole sempre la chiave WPA: si rimanda quella attuale, invariata
            await nebula.call(key, "PATCH", f"/v1/nebula/{site}/ap/wlan-settings", [{
                "id": ssid_id, "wpaKey": current.get("wpaKey") or "",
                "name": body.name if body.name is not None else current["name"],
                "enabled": body.enabled if body.enabled is not None else current["enabled"],
                "guestNetwork": current.get("guestNetwork", False), "tags": current.get("tags") or [],
            }])
        if body.bands is not None:
            if not body.bands:
                raise HTTPException(422, "Serve almeno una banda")
            await nebula.call(key, "PATCH", f"/v1/nebula/{site}/ap/wlan-band-mode",
                              [{"ssid": ssid_id, "enabledBands": body.bands}])
    except NebulaError as exc:
        _fail(exc)
    return {"ok": True}
