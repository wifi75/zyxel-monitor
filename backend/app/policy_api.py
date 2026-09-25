"""API della configurazione centralizzata: profilo del sito, personalizzazioni per AP, applicazione, backup."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import config_items, guard, policy, restore, site_config
from .collectors import ssh
from .core import store
from .core.db import connect
from .core.security import current_user

router = APIRouter(prefix="/api/policy", dependencies=[Depends(current_user)])

Band = Literal["2.4GHz", "5GHz"]


def _configs() -> dict[str, "config_items.RunningConfig"]:
    """Running-config di ogni AP letta al ciclo di lettura SSH (nessuna connessione in più)."""
    out = {}
    for ap in store.list_aps(enabled_only=True):
        _, text = ssh.last_output.get(ap.host, (None, ""))
        start = text.find("show running-config")
        if start >= 0:
            out[ap.name] = config_items.RunningConfig(text[start:])
    return out


def _radio_now(cfg, band: str) -> dict:
    """Canale ("auto" o numero) e larghezza attuali di una banda, dal profilo radio dello slot."""
    slot, key = (1, "2g-channel") if band == "2.4GHz" else (2, "5g-channel")
    prof = cfg.radio_profile(slot) if cfg else None
    if not prof:
        return {"channel": None, "width": None}
    header = f"wlan-radio-profile {prof}"
    auto = cfg.has(header, "dcs activate")
    return {"channel": "auto" if auto else cfg.value(header, key), "width": cfg.value(header, "ch-width")}


@router.get("")
def overview():
    configs = _configs()
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
                "current": {"tx_power": have, **_radio_now(configs.get(ap.name), band)},
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
async def set_site(body: RuleIn, apply: bool = True):
    """apply=false: si salva soltanto (la pagina applica tutte le modifiche insieme con /apply)."""
    value = _validate(body)
    if value is not None and value == policy.UNMANAGED[body.field]:
        value = None       # nel sito "non gestito" è l'assenza della regola
    policy.set_rule(policy.SITE, body.band, body.field, value)
    return {"results": []}      # l'invio agli AP passa sempre da /rollout (prova controllata)


@router.put("/aps/{ap_id}")
async def set_ap(ap_id: int, body: RuleIn, apply: bool = True):
    ap = store.get_ap(ap_id)
    if not ap:
        raise HTTPException(404, "Access point non trovato")
    policy.set_rule(policy.scope_of(ap_id), body.band, body.field, _validate(body))
    return {"results": []}


@router.get("/items")
def list_items():
    values = site_config.load()
    def shown(i):   # la password non esce mai dal server: si dice solo se è impostata
        v = values.get(i.key)
        return (v is not None) if i.kind == "password" else v

    configs = _configs()    # valori attuali letti dagli AP

    def current(i):
        per_ap = {}
        for name, cfg in configs.items():
            v = i.read(cfg)
            per_ap[name] = (v is not None) if i.kind == "password" else v
        return per_ap

    return [{"key": i.key, "section": i.section, "label": i.label, "kind": i.kind, "help": i.help,
             "choices": i.choices, "unit": i.unit, "value": shown(i), "current": current(i)}
            for i in config_items.ITEMS]


class ItemIn(BaseModel):
    value: int | str | bool | list[str] | None = None      # None = non gestito


@router.put("/items/{key}")
async def set_item(key: str, body: ItemIn, apply: bool = True):
    item = config_items.BY_KEY.get(key)
    if not item:
        raise HTTPException(404, "Impostazione sconosciuta")
    try:
        value = None if body.value is None else config_items.parse_value(item, body.value)
    except ValueError as exc:
        raise HTTPException(422, f"{item.label}: {exc}") from None
    site_config.set_value(key, value)
    return {"results": []}


class ApplyItemsIn(BaseModel):
    keys: list[str] | None = None      # None = tutte le voci da mantenere; elenco = solo quelle (anche la password)


class RolloutIn(BaseModel):
    keys: list[str] | None = None     # voci del sito da applicare; None = tutte quelle da mantenere
    radio: bool = False               # anche le regole radio (potenza, canale, larghezza)
    first_ap: int | None = None       # AP su cui provare per primo


@router.get("/guard")
def guard_state():
    return {"enabled": guard.enabled(), "rollout": guard.state, "wait": guard.WAIT, "drop": guard.DROP}


@router.put("/guard")
def guard_set(on: bool):
    guard.set_enabled(on)
    return guard_state()


@router.post("/preview")
async def preview(body: RolloutIn):
    return {"aps": await guard.preview(set(body.keys) if body.keys is not None else None, body.radio)}


@router.delete("/preview")
def preview_cancel():
    guard.cancel_preview()
    return {"ok": True}


@router.post("/rollout")
async def rollout(body: RolloutIn):
    return await guard.start(set(body.keys) if body.keys is not None else None, body.radio, body.first_ap)


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


@router.post("/backups/{backup_id}/restore")
async def restore_backup(backup_id: int):
    """Rimette sull'AP la configurazione Wi-Fi del backup e sospende la gestione del pannello per quell'AP."""
    with connect() as db:
        row = db.execute("SELECT ap FROM config_backups WHERE id = ?", (backup_id,)).fetchone()
    ap = next((a for a in store.list_aps() if row and a.name == row["ap"]), None)
    if not ap or not ap.ssh_password:
        raise HTTPException(404, "AP del backup non trovato o senza SSH")
    return await restore.restore(backup_id, ap)


@router.get("/paused")
def get_paused():
    return {"aps": sorted(restore.paused())}


@router.put("/paused/{ap_name}")
def put_paused(ap_name: str, on: bool):
    restore.set_paused(ap_name, on)
    return {"aps": sorted(restore.paused())}
