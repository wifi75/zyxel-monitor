"""Configurazione centralizzata delle radio, "a stato desiderato" come un controller cloud.

Il profilo del sito vale per tutti gli AP; un AP può personalizzare una banda. Il sistema applica subito
via SSH e, a ogni lettura, confronta il valore reale con quello desiderato: se un AP è tornato indietro
(riavvio, sincronizzazione di Nebula) lo riapplica da solo, con un intervallo minimo per non insistere.
Se dopo l'applicazione l'AP resta su un valore diverso, è il suo limite (es. massimo legale): si segnala
come "limitato" e non si ritenta finché la regola non cambia.
"""
import asyncio
import json
import logging
import time

from .collectors import ssh
from .core import store
from .core.db import connect

log = logging.getLogger("policy")

BANDS = ("2.4GHz", "5GHz")
SITE = "site"
RETRY_AFTER = 900        # secondi fra due riapplicazioni automatiche della stessa regola

# (ap, banda) → (valore desiderato applicato, quando, valore reale prima dell'applicazione)
_applied: dict[tuple[str, str], tuple[int, float, int | None]] = {}


def scope_of(ap_id: int) -> str:
    return f"ap:{ap_id}"


def load() -> dict[str, dict[str, int | None]]:
    """{scope: {banda: dBm}} con solo le righe impostate."""
    out: dict[str, dict[str, int | None]] = {}
    with connect() as db:
        for r in db.execute("SELECT scope, band, tx_power FROM radio_policy"):
            out.setdefault(r["scope"], {})[r["band"]] = r["tx_power"]
    return out


def set_rule(scope: str, band: str, tx_power: int | None, inherit: bool = False) -> None:
    with connect() as db:
        if inherit:
            db.execute("DELETE FROM radio_policy WHERE scope = ? AND band = ?", (scope, band))
        else:
            db.execute(
                "INSERT INTO radio_policy(scope, band, tx_power) VALUES (?,?,?) "
                "ON CONFLICT(scope, band) DO UPDATE SET tx_power = excluded.tx_power",
                (scope, band, tx_power),
            )


def effective(rules: dict, ap_id: int, band: str) -> tuple[int | None, str]:
    """Valore desiderato e sua origine: "ap" (personalizzato), "site" o "none" (non gestito)."""
    own = rules.get(scope_of(ap_id), {})
    if band in own:
        return own[band], "ap"
    if band in rules.get(SITE, {}):
        return rules[SITE][band], "site"
    return None, "none"


def actual_powers() -> dict[str, dict[str, int | None]]:
    """Potenza letta per AP e banda dall'ultimo stato salvato."""
    out: dict[str, dict[str, int | None]] = {}
    with connect() as db:
        for r in db.execute("SELECT ap, radios FROM ap_status"):
            out[r["ap"]] = {x.get("band"): x.get("tx_power") for x in json.loads(r["radios"] or "[]")}
    return out


def status(desired: int | None, actual: int | None, key: tuple[str, str]) -> str:
    if desired is None:
        return "unmanaged"
    if actual is None:
        return "unknown"
    if actual == desired:
        return "ok"
    applied = _applied.get(key)
    if applied and applied[0] == desired and applied[2] == actual:
        return "capped"          # applicato ma l'AP resta dov'era: è il suo limite
    return "pending"


def _event(ap: str, info: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO events(ts, kind, ap, info) VALUES (?,?,?,?)", (int(time.time()), "config", ap, info))


async def apply_ap(ap: store.ApConfig, only_changed: bool = False, reason: str = "manuale") -> dict:
    """Applica all'AP le regole effettive di tutte le bande gestite."""
    if not ap.ssh_password:
        return {"ap": ap.name, "ok": False, "message": "Serve l'accesso SSH per configurare questo AP"}
    rules = load()
    actual = actual_powers().get(ap.name, {})
    commands, changes = [], []
    for band in BANDS:
        want, _ = effective(rules, ap.id, band)
        if want is None:
            continue
        have = actual.get(band)
        if only_changed and have == want:
            continue
        commands += ssh.power_commands(band, want)
        changes.append((band, want, have))
    if not commands:
        return {"ap": ap.name, "ok": True, "message": "Già allineato"}
    try:
        out = await ssh.configure(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port, commands)
    except Exception as exc:     # rete, credenziali, AP spento
        return {"ap": ap.name, "ok": False, "message": f"SSH: {exc}"}
    if m := ssh.CLI_ERROR.search(out):
        return {"ap": ap.name, "ok": False, "message": f"La CLI ha rifiutato il comando ({m.group(1)})"}
    now = time.time()
    for band, want, have in changes:
        _applied[(ap.name, band)] = (want, now, have)
    desc = ", ".join(
        f"{b.replace('GHz', ' GHz')} {w} dBm" + (f" (era {h})" if h is not None else "") for b, w, h in changes
    )
    _event(ap.name, f"Potenza impostata ({reason}): {desc}")
    return {"ap": ap.name, "ok": True, "message": f"Applicato: {desc}"}


async def apply_all(reason: str = "manuale") -> list[dict]:
    aps = [a for a in store.list_aps(enabled_only=True) if a.ssh_password]
    return list(await asyncio.gather(*(apply_ap(a, reason=reason) for a in aps)))


async def enforce() -> None:
    """Chiamata a ogni ciclo: riporta al valore desiderato gli AP che se ne sono allontanati."""
    rules = load()
    if not rules:
        return
    actual = actual_powers()
    now = time.time()
    for ap in store.list_aps(enabled_only=True):
        if not ap.ssh_password:
            continue
        drift = False
        for band in BANDS:
            want, _ = effective(rules, ap.id, band)
            have = actual.get(ap.name, {}).get(band)
            if want is None or have is None or have == want:
                continue
            last = _applied.get((ap.name, band))
            if last and last[0] == want and (last[2] == have or now - last[1] < RETRY_AFTER):
                continue     # limite dell'AP, oppure riapplicato da poco
            drift = True
        if drift:
            result = await apply_ap(ap, only_changed=True, reason="riallineamento automatico")
            if not result["ok"]:
                log.warning("riallineamento %s non riuscito: %s", ap.name, result["message"])


# ---------- backup della configurazione ----------
async def backup_ap(ap: store.ApConfig) -> dict:
    if not ap.ssh_password:
        return {"ap": ap.name, "ok": False, "message": "Serve l'accesso SSH"}
    try:
        text = await ssh.running_config(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port)
    except Exception as exc:
        return {"ap": ap.name, "ok": False, "message": f"SSH: {exc}"}
    if "wlan-ssid-profile" not in text:
        return {"ap": ap.name, "ok": False, "message": "Risposta incompleta: backup non salvato"}
    with connect() as db:
        db.execute("INSERT INTO config_backups(ap, ts, text) VALUES (?,?,?)", (ap.name, int(time.time()), text))
    return {"ap": ap.name, "ok": True, "message": f"Salvato ({len(text.splitlines())} righe)"}


async def backup_all() -> list[dict]:
    aps = [a for a in store.list_aps(enabled_only=True) if a.ssh_password]
    return list(await asyncio.gather(*(backup_ap(a) for a in aps)))
