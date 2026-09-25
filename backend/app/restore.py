"""Ripristino di un backup della running-config su un AP, e pausa della gestione centralizzata.

Si confrontano i blocchi Wi-Fi ("wlan …": slot, profili radio, SSID, sicurezza, filtri MAC) del backup con
quelli attuali e si inviano solo le righe diverse, in una sola sessione (ogni ingresso in un profilo
ricarica le radio). Dopo il ripristino l'AP va "in pausa": il pannello non gli riapplica più le
impostazioni del sito finché non si riprende la gestione, altrimenti annullerebbe il ripristino.
"""
import json
import time

from . import config_items as ci
from .collectors import ssh
from .core.db import connect

PAUSED_KEY = "config_paused"


def paused() -> set[str]:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (PAUSED_KEY,)).fetchone()
    try:
        return set(json.loads(row["value"])) if row else set()
    except ValueError:
        return set()


def set_paused(ap: str, on: bool) -> None:
    names = paused()
    names = names | {ap} if on else names - {ap}
    with connect() as db:
        db.execute("INSERT INTO settings(key, value) VALUES (?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (PAUSED_KEY, json.dumps(sorted(names))))


def _key(line: str) -> str:
    """Parte della riga che identifica l'impostazione ("output-power 19dBm" → "output-power")."""
    parts = line.split()
    return " ".join(parts[:-1]) if len(parts) > 1 else line


def restore_commands(backup: ci.RunningConfig, current: ci.RunningConfig) -> list[str]:
    out: list[str] = []
    for header, old in backup.blocks.items():
        if not header.startswith("wlan"):
            continue
        now = current.block(header)
        if old == now:
            continue
        old_keys = {_key(x) for x in old}
        cmds = [f"no {x}" for x in now if x not in old and _key(x) not in old_keys and not x.startswith("no ")]
        cmds += [x for x in old if x not in now]
        if cmds:
            out += [header, *cmds, "exit"]
    return out


async def restore(backup_id: int, ap) -> dict:
    with connect() as db:
        row = db.execute("SELECT * FROM config_backups WHERE id = ?", (backup_id,)).fetchone()
    if not row:
        return {"ok": False, "message": "Backup non trovato"}
    backup = ci.RunningConfig(row["text"])
    current = ci.RunningConfig(await ssh.running_config(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port))
    commands = restore_commands(backup, current)
    set_paused(ap.name, True)
    if not commands:
        return {"ok": True, "message": "L'AP ha già la configurazione Wi-Fi del backup", "commands": []}
    output = await ssh.configure(ap.host, ap.ssh_user, ap.ssh_password, ap.ssh_port, commands)
    errors = [x for x in output.splitlines() if ssh.CLI_ERROR.search(x)]
    when = time.strftime("%d/%m %H:%M", time.localtime(row["ts"]))
    with connect() as db:
        db.execute("INSERT INTO events(ts, kind, ap, info) VALUES (?,?,?,?)",
                   (int(time.time()), "config", ap.name, f"Ripristinato il backup del {when}"))
    return {"ok": not errors, "message": "; ".join(errors[:3]) or f"Ripristinate {len(commands)} righe",
            "commands": commands}
