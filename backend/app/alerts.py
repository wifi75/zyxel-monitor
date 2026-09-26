"""Avvisi su Telegram: AP offline, linea caduta, dispositivi nuovi, canali saturi, report settimanale.

Si parte dagli eventi già registrati dal poller (tabella events), letti in ordine di id: nessun evento
viene perso né mandato due volte, anche dopo un riavvio del server. Un AP che cade e torna entro
la tolleranza (una lettura SSH andata a vuoto) non genera avvisi.
"""
import asyncio
import datetime as dt
import html
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import truststore
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .channels import BUSY_PCT
from .core.config import get_settings
from .core.db import connect
from .core.security import current_user

log = logging.getLogger("alerts")
router = APIRouter(prefix="/api/alerts", dependencies=[Depends(current_user)])

KINDS = ("ap_down", "ap_up", "wan_down", "wan_up", "new_device", "config", "busy")
DEFAULT_KINDS = ("ap_down", "ap_up", "wan_down", "wan_up", "new_device", "config")
WEEKLY_HOUR = 9           # lunedì, ora locale
BUSY_COOLDOWN = 6 * 3600  # un canale saturo si segnala al massimo ogni 6 ore per AP e banda

LABEL = {
    "ap_down": "🔴 AP offline", "ap_up": "🟢 AP di nuovo online", "wan_down": "🔴 Linea Internet caduta",
    "wan_up": "🟢 Linea Internet tornata", "new_device": "🆕 Dispositivo nuovo", "config": "⚙️ Configurazione",
}


# ---------- impostazioni (tabella settings, chiavi alert_*) ----------
def _get(db, key: str, default: str = "") -> str:
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _put(db, key: str, value: str) -> None:
    db.execute("INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
               (key, value))


def config() -> dict:
    with connect() as db:
        return {
            "token": _get(db, "alert_telegram_token"),
            "chat_id": _get(db, "alert_telegram_chat"),
            "kinds": json.loads(_get(db, "alert_kinds", json.dumps(DEFAULT_KINDS))),
            "weekly": _get(db, "alert_weekly", "true") == "true",
        }


def enabled(cfg: dict | None = None) -> bool:
    cfg = cfg or config()
    return bool(cfg["token"] and cfg["chat_id"])


# ---------- invio ----------
def _post(token: str, chat_id: str, text: str) -> None:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:     # 401 token errato, 400 chat inesistente: il motivo è nel corpo
        body = json.loads(exc.read() or b"{}")
    if not body.get("ok"):
        raise RuntimeError(body.get("description") or "risposta di Telegram non valida")


async def send(text: str, cfg: dict | None = None) -> None:
    cfg = cfg or config()
    await asyncio.get_running_loop().run_in_executor(None, _post, cfg["token"], cfg["chat_id"], text)


# ---------- regole ----------
def _grace() -> int:
    return get_settings().poll_interval + 45


def pending_events(rows: list[dict], now: int, grace: int) -> tuple[list[dict], int | None]:
    """Eventi da segnalare e ultimo id consumato. Gli eventi più giovani di `grace` aspettano il giro dopo;
    una caduta di AP seguita dal rientro entro `grace` si annulla (coppia ap_down/ap_up)."""
    ready: list[dict] = []
    for r in rows:              # in ordine di id: ci si ferma al primo troppo recente
        if now - r["ts"] < grace:
            break
        ready.append(r)
    if not ready:
        return [], None
    drop: set[int] = set()
    for i, r in enumerate(ready):
        if r["kind"] != "ap_down":
            continue
        back = next((x for x in ready[i + 1:] if x["kind"] == "ap_up" and x["ap"] == r["ap"]), None)
        if back and back["ts"] - r["ts"] < grace:
            drop |= {r["id"], back["id"]}
    return [r for r in ready if r["id"] not in drop], ready[-1]["id"]


def _format(ev: dict) -> str:
    who = html.escape(ev.get("name") or ev.get("ap") or "")
    when = dt.datetime.fromtimestamp(ev["ts"]).strftime("%H:%M")
    extra = ev.get("info") or ""
    if ev["kind"] == "new_device" and ev.get("ap"):
        extra = f"su {ev['ap']}" + (f", IP {extra}" if extra else "")
    tail = f" — {html.escape(extra)}" if extra else ""
    return f"{LABEL.get(ev['kind'], ev['kind'])}: <b>{who}</b> alle {when}{tail}"


_busy_sent: dict[tuple[str, str], float] = {}


def busy_radios(kinds: list[str]) -> list[str]:
    if "busy" not in kinds:
        return []
    out = []
    now = time.time()
    with connect() as db:
        rows = db.execute("SELECT ap, radios FROM ap_status WHERE online = 1").fetchall()
    for r in rows:
        for radio in json.loads(r["radios"] or "[]"):
            pct = radio.get("utilization")
            key = (r["ap"], radio.get("band"))
            if pct is not None and pct >= BUSY_PCT and now - _busy_sent.get(key, 0) > BUSY_COOLDOWN:
                _busy_sent[key] = now
                out.append(f"📶 Canale saturo: <b>{html.escape(r['ap'])}</b> {radio.get('band')} "
                           f"canale {radio.get('channel') or '?'} occupato al {pct}%")
    return out


async def check() -> None:
    """Chiamato dal poller a ogni ciclo."""
    cfg = config()
    now = int(time.time())
    with connect() as db:
        last = _get(db, "alert_last_event")
        if not last:   # prima volta: si parte da adesso, non si ripescano settimane di storico
            _put(db, "alert_last_event", str(db.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]))
            return
        rows = [dict(r) for r in db.execute("SELECT * FROM events WHERE id > ? ORDER BY id LIMIT 500", (int(last),))]
    events, last_id = pending_events(rows, now, _grace())
    lines = [_format(e) for e in events if e["kind"] in cfg["kinds"]]
    lines += busy_radios(cfg["kinds"]) if enabled(cfg) else []
    if lines and enabled(cfg):
        try:
            await send("\n".join(lines), cfg)
        except Exception as exc:     # Telegram irraggiungibile: gli eventi si riprovano al giro dopo
            log.warning("invio avviso non riuscito: %s", exc)
            return
    if last_id is not None:
        with connect() as db:
            _put(db, "alert_last_event", str(last_id))
    await _weekly(cfg)


async def _weekly(cfg: dict) -> None:
    from . import report   # qui e non in cima: report importa il poller, che importa questo modulo
    if not (cfg["weekly"] and enabled(cfg)):
        return
    today = dt.datetime.now()
    if today.weekday() != 0 or today.hour < WEEKLY_HOUR:
        return
    week = today.strftime("%G-%V")
    with connect() as db:
        if _get(db, "alert_last_weekly") == week:
            return
    try:
        await send(report.as_text(report.build(7)), cfg)
    except Exception as exc:
        log.warning("report settimanale non inviato: %s", exc)
        return
    with connect() as db:
        _put(db, "alert_last_weekly", week)


# ---------- API ----------
class AlertsIn(BaseModel):
    token: str = Field("", max_length=200)       # vuoto = resta quello salvato
    chat_id: str = Field("", max_length=64)
    kinds: list[str] = Field(default_factory=lambda: list(DEFAULT_KINDS))
    weekly: bool = True
    clear_token: bool = False


def _public(cfg: dict) -> dict:
    return {"has_token": bool(cfg["token"]), "chat_id": cfg["chat_id"], "kinds": cfg["kinds"],
            "weekly": cfg["weekly"], "all_kinds": list(KINDS), "enabled": enabled(cfg)}


@router.get("")
def get_alerts():
    return _public(config())


@router.put("")
def save_alerts(body: AlertsIn):
    with connect() as db:
        if body.clear_token:
            _put(db, "alert_telegram_token", "")
        elif body.token.strip():
            _put(db, "alert_telegram_token", body.token.strip())
        _put(db, "alert_telegram_chat", body.chat_id.strip())
        _put(db, "alert_kinds", json.dumps([k for k in body.kinds if k in KINDS]))
        _put(db, "alert_weekly", "true" if body.weekly else "false")
    return _public(config())


@router.post("/test")
async def test_alerts(body: AlertsIn):
    cfg = config()
    token = body.token.strip() or cfg["token"]
    chat = body.chat_id.strip() or cfg["chat_id"]
    if not (token and chat):
        return {"ok": False, "message": "Servono il token del bot e l'id della chat"}
    try:
        await send("✅ Zyxel Monitor: gli avvisi arrivano qui.", {"token": token, "chat_id": chat})
    except Exception as exc:
        return {"ok": False, "message": f"Telegram: {exc}"}
    return {"ok": True, "message": "Messaggio di prova inviato"}


@router.post("/report")
async def send_report_now():
    from . import report
    cfg = config()
    if not enabled(cfg):
        return {"ok": False, "message": "Telegram non configurato"}
    try:
        await send(report.as_text(report.build(7)), cfg)
    except Exception as exc:
        return {"ok": False, "message": f"Telegram: {exc}"}
    return {"ok": True, "message": "Report inviato"}
