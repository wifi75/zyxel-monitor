"""API della configurazione centralizzata: profilo del sito, personalizzazioni per AP, applicazione, backup."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import policy
from .core import store
from .core.db import connect
from .core.security import current_user

router = APIRouter(prefix="/api/policy", dependencies=[Depends(current_user)])

Band = Literal["2.4GHz", "5GHz"]


@router.get("")
def overview():
    rules = policy.load()
    actual = policy.actual_powers()
    aps = []
    for ap in store.list_aps():
        bands = {}
        for band in policy.BANDS:
            want, source = policy.effective(rules, ap.id, band)
            have = actual.get(ap.name, {}).get(band)
            own = rules.get(policy.scope_of(ap.id), {}).get(band, {})
            bands[band] = {
                "desired": want, "source": source, "actual": have,
                "status": policy.status(want, have, (ap.name, band)),
                "override": {f: own.get(f) for f in policy.FIELDS},   # None = come il sito
            }
        aps.append({"id": ap.id, "name": ap.name, "method": ap.method, "enabled": ap.enabled,
                    "configurable": bool(ap.ssh_password), "bands": bands})
    site = {b: {f: rules.get(policy.SITE, {}).get(b, {}).get(f) for f in policy.FIELDS} for b in policy.BANDS}
    return {"site": site, "aps": aps}


CHANNELS = {
    "2.4GHz": {str(c) for c in range(1, 14)},
    "5GHz": {str(c) for c in (36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140)},
}
WIDTHS = {"2.4GHz": {"20", "20/40"}, "5GHz": {"20", "20/40", "20/40/80"}}


class RuleIn(BaseModel):
    band: Band
    field: Literal["tx_power", "channel", "width"]
    value: int | str | None = None    # None = sito: non gestito / AP: come il sito; "none" = AP: non gestito


def _validate(body: RuleIn):
    v = body.value
    if v is None:
        return None
    if v == "none":
        return policy.UNMANAGED[body.field]
    if body.field == "tx_power":
        if not isinstance(v, int) or not 1 <= v <= 30:
            raise HTTPException(422, "Potenza fra 1 e 30 dBm")
        return v
    v = str(v)
    allowed = {"auto", *CHANNELS[body.band]} if body.field == "channel" else WIDTHS[body.band]
    if v not in allowed:
        raise HTTPException(422, f"Valore non valido per la {body.band}")
    return v


@router.put("/site")
async def set_site(body: RuleIn):
    value = _validate(body)
    if value is not None and value == policy.UNMANAGED[body.field]:
        value = None       # nel sito "non gestito" è l'assenza della regola
    policy.set_rule(policy.SITE, body.band, body.field, value)
    return {"results": await policy.apply_all(reason="profilo del sito")}


@router.put("/aps/{ap_id}")
async def set_ap(ap_id: int, body: RuleIn):
    ap = store.get_ap(ap_id)
    if not ap:
        raise HTTPException(404, "Access point non trovato")
    policy.set_rule(policy.scope_of(ap_id), body.band, body.field, _validate(body))
    return {"results": [await policy.apply_ap(ap, reason="personalizzazione")]}


@router.post("/apply")
async def apply_now():
    return {"results": await policy.apply_all()}


@router.post("/backups")
async def backup_now():
    return {"results": await policy.backup_all()}


@router.get("/backups")
def list_backups():
    with connect() as db:
        rows = db.execute(
            "SELECT id, ap, ts, length(text) AS size FROM config_backups ORDER BY ts DESC LIMIT 100"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/backups/{backup_id}")
def get_backup(backup_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM config_backups WHERE id = ?", (backup_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Backup non trovato")
    return dict(row)
