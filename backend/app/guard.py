"""Protezioni della configurazione centralizzata.

1. Interruttore generale: finché la gestione è spenta il pannello solo monitora e non invia nulla agli AP.
2. Anteprima: i comandi che verrebbero inviati a ogni AP, senza inviarli (le password sono mascherate).
3. Prova su un AP: la modifica va prima su un AP; dopo WAIT secondi si confrontano i dispositivi collegati
   a tutto il sito e solo se non sono calati si passa agli altri.
4. Ripristino automatico: se i dispositivi calano oltre DROP, ogni AP toccato torna al backup fatto subito
   prima e va in pausa. In ogni caso si elencano i dispositivi che non sono rientrati.
Durante una prova e un'anteprima aperta il riallineamento automatico è sospeso.
"""
import asyncio
import logging
import re
import time

from . import policy, restore, site_config
from .core import store
from .core.db import connect

log = logging.getLogger("guard")

ENABLED_KEY = "config_enabled"
WAIT = 300          # secondi di osservazione dopo ogni passo
DROP = 0.30         # calo dei dispositivi collegati oltre il quale si ripristina
HOLD = 600          # durata massima di un'anteprima aperta
GUARD_REASON = "prova controllata"

state: dict = {"status": "idle"}      # idle | running | done | rolled_back | error
_hold_until = 0.0
_task: asyncio.Task | None = None


# ---------- interruttore generale ----------
def enabled() -> bool:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (ENABLED_KEY,)).fetchone()
    return bool(row and row["value"] == "true")


def set_enabled(on: bool) -> None:
    with connect() as db:
        db.execute("INSERT INTO settings(key, value) VALUES (?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (ENABLED_KEY, "true" if on else "false"))


def blocked(reason: str) -> str | None:
    """Motivo per cui non si può inviare nulla agli AP adesso, None se si può."""
    if not enabled():
        return "Gestione dal pannello spenta: il pannello solo monitora"
    if reason == GUARD_REASON:
        return None
    if state.get("status") == "running":
        return "Prova controllata in corso: si attende la verifica"
    if time.time() < _hold_until:
        return "Anteprima aperta: si attende la conferma"
    return None


# ---------- anteprima ----------
_SECRET = re.compile(r"^(\s*(?:encrypted-)?wpa-psk\s+).*$")


def _mask(commands: list[str]) -> list[str]:
    return [_SECRET.sub(r"\1••••••••", c) for c in commands]


def _targets() -> list[store.ApConfig]:
    skip = restore.paused()
    return [a for a in store.list_aps(enabled_only=True) if a.ssh_password and a.name not in skip]


async def _plan(ap: store.ApConfig, keys: set[str] | None, radio: bool) -> dict:
    parts, commands = [], []
    if radio:
        r = await policy.apply_ap(ap, dry_run=True)
        commands += r.get("commands", [])
        if r.get("commands"):
            parts.append(r["message"])
        elif not r["ok"]:
            parts.append(r["message"])
    if keys is None or keys:
        r = await site_config.apply_ap(ap, only=keys, dry_run=True)
        commands += r.get("commands", [])
        if r.get("commands"):
            parts.append(r["message"])
        elif not r["ok"]:
            parts.append(r["message"])
    return {"ap": ap.name, "id": ap.id, "changes": "; ".join(parts), "commands": _mask(commands)}


async def preview(keys: set[str] | None, radio: bool) -> list[dict]:
    global _hold_until
    _hold_until = time.time() + HOLD
    return list(await asyncio.gather(*(_plan(a, keys, radio) for a in _targets())))


def cancel_preview() -> None:
    global _hold_until
    _hold_until = 0.0


# ---------- prova controllata ----------
def _snapshot() -> dict[str, str]:
    """{mac: nome} dei dispositivi collegati adesso a tutto il sito."""
    with connect() as db:
        rows = db.execute("SELECT c.mac, COALESCE(a.name, c.hostname, c.ip, c.mac) AS name "
                          "FROM clients c LEFT JOIN aliases a ON a.mac = c.mac").fetchall()
    return {r["mac"]: r["name"] for r in rows}


def _event(info: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO events(ts, kind, ap, info) VALUES (?,?,?,?)", (int(time.time()), "config", "", info))


async def _apply(ap: store.ApConfig, keys: set[str] | None, radio: bool) -> tuple[dict, int | None]:
    """Backup e applicazione su un AP; restituisce (esito, id del backup)."""
    b = await policy.backup_ap(ap)
    if not b["ok"]:
        return {"ap": ap.name, "ok": False, "message": f"Backup non riuscito, AP saltato: {b['message']}"}, None
    msgs, ok = [], True
    if radio:
        r = await policy.apply_ap(ap, reason=GUARD_REASON)
        ok &= r["ok"]
        msgs.append(r["message"])
    if keys is None or keys:
        r = await site_config.apply_ap(ap, reason=GUARD_REASON, only=keys)
        ok &= r["ok"]
        msgs.append(r["message"])
    return {"ap": ap.name, "ok": ok, "message": "; ".join(msgs)}, b.get("id")


async def _observe(before: dict[str, str], phase: str) -> tuple[bool, list[str]]:
    """Attende WAIT secondi e dice se i dispositivi sono rimasti (True) e quali non sono rientrati."""
    state.update(phase=phase, check_at=int(time.time() + WAIT))
    await asyncio.sleep(WAIT - 40)
    from .poller import poll_now
    poll_now()                     # lettura fresca subito prima della verifica
    await asyncio.sleep(40)
    after = _snapshot()
    lost = sorted(name for mac, name in before.items() if mac not in after)
    state.update(clients_after=len(after), lost=lost)
    good = len(before) < 3 or len(after) >= len(before) * (1 - DROP)
    return good, lost


async def _rollback(backups: dict[str, int]) -> list[str]:
    msgs = []
    aps = {a.name: a for a in store.list_aps()}
    for name, bid in backups.items():
        try:
            r = await restore.restore(bid, aps[name])
            msgs.append(f"{name}: {r['message']}")
        except Exception as exc:     # l'AP potrebbe essere irraggiungibile proprio per la modifica
            msgs.append(f"{name}: ripristino non riuscito ({exc})")
    return msgs


async def _run(keys: set[str] | None, radio: bool, first_id: int | None) -> None:
    targets = _targets()
    first = next((a for a in targets if a.id == first_id), targets[0] if targets else None)
    if not first:
        state.update(status="error", message="Nessun AP configurabile")
        return
    before = _snapshot()
    state.update(status="running", first=first.name, clients_before=len(before), results=[], lost=[])
    res, bid = await _apply(first, keys, radio)
    state["results"].append(res)
    backups = {first.name: bid} if bid else {}
    good, lost = await _observe(before, f"prova su {first.name}")
    if not good:
        msgs = await _rollback(backups)
        state.update(status="rolled_back", message="Dispositivi calati dopo la prova: ripristinato. " + "; ".join(msgs))
        _event(f"Prova su {first.name} annullata, dispositivi non rientrati: {', '.join(lost) or '—'}")
        return
    others = [a for a in targets if a.id != first.id]
    before = _snapshot()
    state["clients_before"] = len(before)
    for ap in others:
        # backup e invio via SSH richiedono un po' per ogni AP: si dice su quale si sta lavorando
        state.update(phase=f"applico su {ap.name}", check_at=None)
        res, bid = await _apply(ap, keys, radio)
        state["results"].append(res)
        if bid:
            backups[ap.name] = bid
    if others:
        good, lost2 = await _observe(before, "verifica su tutti gli AP")
        lost = sorted(set(lost) | set(lost2))
        if not good:
            msgs = await _rollback({k: v for k, v in backups.items() if k != first.name})
            state.update(status="rolled_back", message="Dispositivi calati dopo l'estensione agli altri AP: "
                         "ripristinati tutti tranne quello di prova. " + "; ".join(msgs))
            _event(f"Estensione annullata, dispositivi non rientrati: {', '.join(lost) or '—'}")
            return
    state.update(status="done", message="Applicato su tutti gli AP", lost=lost)
    _event("Modifica applicata con prova controllata" + (f"; non rientrati: {', '.join(lost)}" if lost else ""))


async def start(keys: set[str] | None, radio: bool, first_id: int | None) -> dict:
    global _task, _hold_until
    if state.get("status") == "running":
        return {"ok": False, "message": "C'è già una prova in corso"}
    if why := blocked(GUARD_REASON):
        return {"ok": False, "message": why}
    _hold_until = 0.0
    state.clear()
    state.update(status="running", started=int(time.time()))

    async def runner():
        try:
            await _run(keys, radio, first_id)
        except Exception as exc:
            log.exception("prova controllata")
            state.update(status="error", message=str(exc))

    _task = asyncio.create_task(runner())
    return {"ok": True, "message": "Prova avviata"}
