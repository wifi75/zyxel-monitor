"""API della configurazione centralizzata: profilo del sito, personalizzazioni per AP, applicazione, backup."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
            own = rules.get(policy.scope_of(ap.id), {})
            bands[band] = {"desired": want, "source": source, "actual": have,
                           "override": own[band] if band in own else "inherit",
                           "status": policy.status(want, have, (ap.name, band))}
        aps.append({"id": ap.id, "name": ap.name, "method": ap.method, "enabled": ap.enabled,
                    "configurable": bool(ap.ssh_password), "bands": bands})
    return {"site": {b: rules.get(policy.SITE, {}).get(b) for b in policy.BANDS}, "aps": aps}


class RuleIn(BaseModel):
    band: Band
    tx_power: int | None = Field(None, ge=1, le=30)   # None = non gestito
    inherit: bool = False                            # solo per gli AP: torna al valore del sito


@router.put("/site")
async def set_site(body: RuleIn):
    policy.set_rule(policy.SITE, body.band, body.tx_power, inherit=body.tx_power is None)
    return {"results": await policy.apply_all(reason="profilo del sito")}


@router.put("/aps/{ap_id}")
async def set_ap(ap_id: int, body: RuleIn):
    ap = store.get_ap(ap_id)
    if not ap:
        raise HTTPException(404, "Access point non trovato")
    policy.set_rule(policy.scope_of(ap_id), body.band, body.tx_power, inherit=body.inherit)
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
