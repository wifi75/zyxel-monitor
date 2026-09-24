"""Impostazioni del sito (config_items) applicate a tutti gli AP e mantenute nel tempo.

Si confronta il valore voluto con quello letto dalla running-config di ogni AP: si inviano solo i comandi
delle voci diverse. Il controllo periodico (ogni 15 minuti) riallinea gli AP che Nebula o un riavvio
hanno riportato indietro.
"""
import asyncio
import json
import logging
import time

from . import config_items as ci
from .collectors import ssh
from .core import store
from .core.db import connect

log = logging.getLogger("site_config")
CHECK_EVERY = 900
_last_check = 0.0


def load() -> dict[str, object]:
    with connect() as db:
        return {r["key"]: json.loads(r["value"]) for r in db.execute("SELECT key, value FROM site_config")}


def set_value(key: str, value) -> None:
    with connect() as db:
        if value is None:
            db.execute("DELETE FROM site_config WHERE key = ?", (key,))
        else:
            db.execute(
                "INSERT INTO site_config(key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )


def _event(ap: str, info: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO events(ts, kind, ap, info) VALUES (?,?,?,?)", (int(time.time()), "config", ap, info))


async def apply_ap(ap: store.ApConfig, reason: str = "manuale", only: set[str] | None = None) -> dict:
    """only = voci da applicare (quella appena cambiata); None = controllo periodico delle voci da mantenere.
    Ogni ingresso in un profilo ricarica le radio dell'AP per qualche secondo: si inviano solo le differenze."""
    wanted = load()
    if only is not None:
        wanted = {k: v for k, v in wanted.items() if k in only}
    if not wanted:
        return {"ap": ap.name, "ok": True, "message": "Nessuna impostazione del sito"}
    if not ap.ssh_password:
        return {"ap": ap.name, "ok": False, "message": "Serve l'accesso SSH per configurare questo AP"}
    try:
        cfg = ci.RunningConfig(await ssh.running_config(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port))
    except Exception as exc:
        return {"ap": ap.name, "ok": False, "message": f"SSH: {exc}"}
    commands, changed = [], []
    for key, value in wanted.items():
        item = ci.BY_KEY.get(key)
        if not item or (only is None and not item.enforce):
            continue
        if key == "hostname_sync":
            cmds = ci.hostname_commands(ap.name, cfg) if value else []
        elif item.enforce and ci.same(item, value, item.read(cfg)):
            continue
        else:
            cmds = item.build(value, cfg)
        if cmds:
            commands += cmds
            changed.append(item.label)
    if not commands:
        return {"ap": ap.name, "ok": True, "message": "Già allineato"}
    try:
        out = await ssh.configure(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port, commands)
    except Exception as exc:
        return {"ap": ap.name, "ok": False, "message": f"SSH: {exc}"}
    if m := ssh.CLI_ERROR.search(out):
        return {"ap": ap.name, "ok": False, "message": f"La CLI ha rifiutato un comando ({m.group(1)})"}
    desc = ", ".join(changed)
    _event(ap.name, f"Impostazioni del sito applicate ({reason}): {desc}")
    return {"ap": ap.name, "ok": True, "message": f"Applicato: {desc}"}


async def apply_all(reason: str = "manuale", only: set[str] | None = None) -> list[dict]:
    aps = [a for a in store.list_aps(enabled_only=True) if a.ssh_password]
    return list(await asyncio.gather(*(apply_ap(a, reason, only) for a in aps)))


async def enforce() -> None:
    """Ogni 15 minuti: rilegge la configurazione degli AP e riapplica le voci cambiate."""
    global _last_check
    if time.time() - _last_check < CHECK_EVERY or not load():
        return
    _last_check = time.time()
    for r in await apply_all("riallineamento automatico"):
        if not r["ok"]:
            log.warning("riallineamento %s non riuscito: %s", r["ap"], r["message"])


async def current_values(ap: store.ApConfig) -> dict[str, object]:
    """Valori attuali letti da un AP (per mostrare lo stato nel pannello)."""
    cfg = ci.RunningConfig(await ssh.running_config(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port))
    return {i.key: i.read(cfg) for i in ci.ITEMS}


def explore_commands(cfg: ci.RunningConfig) -> list[str]:
    """Solo richieste di aiuto ("?") dentro i profili già esistenti: non cambiano nulla."""
    lines = ["configure terminal"]
    for header in (f"wlan-security-profile {cfg.security_profile()}", f"wlan-ssid-profile {cfg.ssid_profile()}",
                   "wlan-macfilter-profile BLOCKED1", f"wlan-radio-profile {cfg.radio_profile(1)}"):
        if "None" not in header:
            lines += [header, "?", "exit"]
    return [*lines, "exit"]
