"""Endpoint REST della dashboard."""
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .core.db import connect
from .core.security import (
    MIN_PASSWORD_LEN, create_token, current_user, hash_password, verify_password,
)
from .core.version import APP_AUTHOR, APP_NAME, APP_VERSION
from .devices import device_type
from .poller import INTERNET, internet_state

router = APIRouter(prefix="/api")


def _build_id() -> str:
    """Impronta dell'interfaccia servita: Vite rinomina gli asset a ogni build, quindi index.html cambia
    a ogni deploy anche a parità di versione. La pagina aperta la confronta per ricaricarsi da sola."""
    index = Path(__file__).resolve().parent.parent / "static" / "index.html"
    try:
        return hashlib.sha1(index.read_bytes()).hexdigest()[:12]
    except OSError:
        return APP_VERSION


BUILD_ID = _build_id()


@router.get("/health")
def health():
    return {"status": "ok", "name": APP_NAME, "version": APP_VERSION, "author": APP_AUTHOR, "build": BUILD_ID}


# ---------- autenticazione ----------
class LoginIn(BaseModel):
    username: str
    password: str


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LEN)


@router.post("/login")
def login(body: LoginIn):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Credenziali non valide")
    return {"token": create_token(row["username"]), "default_password": bool(row["is_default"])}


@router.get("/me")
def me(user: str = Depends(current_user)):
    with connect() as db:
        row = db.execute("SELECT is_default FROM users WHERE username = ?", (user,)).fetchone()
    return {"username": user, "default_password": bool(row and row["is_default"])}


@router.post("/password")
def change_password(body: PasswordIn, user: str = Depends(current_user)):
    with connect() as db:
        row = db.execute("SELECT password_hash FROM users WHERE username = ?", (user,)).fetchone()
        if not row or not verify_password(body.old_password, row["password_hash"]):
            raise HTTPException(400, "Password attuale errata")
        db.execute(
            "UPDATE users SET password_hash = ?, is_default = 0 WHERE username = ?",
            (hash_password(body.new_password), user),
        )
    return {"ok": True}


# ---------- dati ----------
@router.get("/aps", dependencies=[Depends(current_user)])
def list_aps():
    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM ap_status ORDER BY ap")]
    for r in rows:
        r["radios"] = json.loads(r["radios"] or "[]")
        r["online"] = bool(r["online"])
    return rows


@router.get("/clients", dependencies=[Depends(current_user)])
def list_clients():
    with connect() as db:
        rows = db.execute(
            """SELECT c.*, a.name AS alias FROM clients c
               LEFT JOIN aliases a ON a.mac = c.mac ORDER BY c.ap, c.rssi_dbm DESC"""
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["device_type"] = device_type(d["alias"] or d["hostname"], d["mac"])
        out.append(d)
    return out


class AliasIn(BaseModel):
    name: str = Field(max_length=60)


@router.put("/clients/{mac}/alias", dependencies=[Depends(current_user)])
def set_alias(mac: str, body: AliasIn):
    mac = mac.lower()
    with connect() as db:
        if body.name.strip():
            db.execute(
                "INSERT INTO aliases(mac, name) VALUES (?,?) ON CONFLICT(mac) DO UPDATE SET name=excluded.name",
                (mac, body.name.strip()),
            )
        else:
            db.execute("DELETE FROM aliases WHERE mac = ?", (mac,))
    return {"ok": True}


@router.get("/events", dependencies=[Depends(current_user)])
def list_events(limit: int = 200, mac: str | None = None, ap: str | None = None):
    limit = max(1, min(limit, 1000))
    where, args = [], []
    if mac:
        where.append("mac = ?")
        args.append(mac.lower())
    if ap:
        where.append("ap = ?")
        args.append(ap)
    sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "")
    with connect() as db:
        rows = db.execute(sql + " ORDER BY ts DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]


@router.get("/usage", dependencies=[Depends(current_user)])
def usage(hours: float = 24):
    """Byte Wi-Fi scambiati nel periodo, per AP e per SSID (somma degli incrementi dei contatori)."""
    since = int(time.time() - max(0.25, min(hours, 24 * 30)) * 3600)
    with connect() as db:
        rows = db.execute(
            """SELECT ts, ap, iface, in_bytes, out_bytes FROM samples
               WHERE ts >= ? AND iface LIKE 'wlan-%' AND ap <> '_internet'
               ORDER BY ap, iface, ts""",
            (since,),
        ).fetchall()
    per_ap: dict[str, dict[str, int]] = defaultdict(lambda: {"down": 0, "up": 0})
    prev: dict[tuple[str, str], tuple[int, int]] = {}
    for r in rows:
        key = (r["ap"], r["iface"])
        p = prev.get(key)
        prev[key] = (r["in_bytes"], r["out_bytes"])
        if not p:
            continue
        d_in, d_out = r["in_bytes"] - p[0], r["out_bytes"] - p[1]
        if d_in >= 0 and d_out >= 0:
            per_ap[r["ap"]]["up"] += d_in
            per_ap[r["ap"]]["down"] += d_out
    return {"hours": hours, "per_ap": per_ap}


@router.get("/sites", dependencies=[Depends(current_user)])
def sites(hours: float = 24, ap: str | None = None, ip: str | None = None, limit: int = 10):
    """Siti più richiesti dai client Wi-Fi (query DNS da OPNsense).
    Si contano solo i dispositivi connessi ora agli AP (esclusi server e PC via cavo);
    con `ap` solo quelli di quell'AP, con `ip` solo quel dispositivo."""
    since = int(time.time() - max(0.25, min(hours, 24 * 30)) * 3600)
    limit = max(1, min(limit, 50))
    ap = ap or None
    with connect() as db:
        if ip:
            rows = db.execute(
                """SELECT site, COUNT(*) AS n FROM dns WHERE ts >= ? AND client_ip = ?
                   GROUP BY site ORDER BY n DESC LIMIT ?""",
                (since, ip, limit),
            ).fetchall()
            total = db.execute("SELECT COUNT(*) FROM dns").fetchone()[0]
            return {"available": total > 0, "items": [{"site": r["site"], "queries": r["n"]} for r in rows]}
        rows = db.execute(
            """SELECT site, COUNT(*) AS n FROM dns
               WHERE ts >= ? AND client_ip IN
                     (SELECT ip FROM clients WHERE ip IS NOT NULL AND (? IS NULL OR ap = ?))
               GROUP BY site ORDER BY n DESC LIMIT ?""",
            (since, ap, ap, limit),
        ).fetchall()
        total = db.execute("SELECT COUNT(*) FROM dns").fetchone()[0]
    return {"available": total > 0, "items": [{"site": r["site"], "queries": r["n"]} for r in rows]}


@router.get("/traffic", dependencies=[Depends(current_user)])
def traffic(hours: float = 6, points: int = 120):
    """Traffico Wi-Fi (somma delle interfacce SSID) e numero di client per AP, in bucket temporali."""
    hours = max(0.25, min(hours, 24 * 30))
    points = max(10, min(points, 500))
    now = int(time.time())
    since = now - int(hours * 3600)
    step = max(60, int(hours * 3600 / points))

    with connect() as db:
        rows = db.execute(
            """SELECT ts, ap, iface, in_bytes, out_bytes FROM samples
               WHERE ts >= ? AND ap <> '_internet' ORDER BY ap, iface, ts""",
            (since - step,),
        ).fetchall()

    # ap -> bucket -> [rx_bytes, tx_bytes]
    rate: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    clients: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    prev: dict[tuple[str, str], tuple] = {}
    for r in rows:
        bucket = (r["ts"] - since) // step * step + since
        if r["iface"] == "_clients":
            clients[r["ap"]][bucket].append(r["in_bytes"])
            continue
        if not r["iface"].startswith("wlan-"):
            continue
        key = (r["ap"], r["iface"])
        p = prev.get(key)
        prev[key] = (r["ts"], r["in_bytes"], r["out_bytes"])
        if not p or r["ts"] <= p[0]:
            continue
        d_in, d_out = r["in_bytes"] - p[1], r["out_bytes"] - p[2]
        if d_in < 0 or d_out < 0:      # contatore azzerato (riavvio AP)
            continue
        acc = rate[r["ap"]][bucket]
        acc[0] += d_in
        acc[1] += d_out

    buckets = list(range(since, now + 1, step))
    series = {}
    for ap in sorted(set(rate) | set(clients)):
        pts = []
        for b in buckets:
            acc = rate[ap].get(b)
            cl = clients[ap].get(b)
            # i byte ricevuti dalla radio sono l'upload dei client, quelli trasmessi il download
            pts.append({
                "ts": b,
                "down_bps": round(acc[1] * 8 / step) if acc else None,
                "up_bps": round(acc[0] * 8 / step) if acc else None,
                "clients": round(sum(cl) / len(cl)) if cl else None,
            })
        series[ap] = pts
    return {"step": step, "series": series}


@router.get("/internet", dependencies=[Depends(current_user)])
def internet(hours: float = 6, points: int = 120):
    """Linea Internet da OPNsense: stato gateway, protezione DNS, velocità WAN nel tempo e GB del periodo."""
    hours = max(0.25, min(hours, 24 * 30))
    points = max(10, min(points, 500))
    now = int(time.time())
    since = now - int(hours * 3600)
    step = max(60, int(hours * 3600 / points))
    with connect() as db:
        rows = db.execute(
            "SELECT ts, in_bytes, out_bytes FROM samples WHERE ap = ? AND iface = 'wan' AND ts >= ? ORDER BY ts",
            (INTERNET, since - step),
        ).fetchall()
    buckets: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    down = up = 0
    for prev, cur in zip(rows, rows[1:], strict=False):
        d_in, d_out = cur["in_bytes"] - prev["in_bytes"], cur["out_bytes"] - prev["out_bytes"]
        if d_in < 0 or d_out < 0 or cur["ts"] < since:
            continue
        b = (cur["ts"] - since) // step * step + since
        buckets[b][0] += d_in
        buckets[b][1] += d_out
        down += d_in
        up += d_out
    series = [
        {"ts": b, "down_bps": round(buckets[b][0] * 8 / step) if b in buckets else None,
         "up_bps": round(buckets[b][1] * 8 / step) if b in buckets else None, "clients": None}
        for b in range(since, now + 1, step)
    ]
    gateways = internet_state.get("gateways", [])
    return {
        "available": bool(internet_state),
        "gateways": gateways,
        "dns": internet_state.get("dns"),
        "period": {"down": down, "up": up},
        "series": series,
        **_line_history(gateways[0]["name"] if gateways else None, since, now, step),
    }


def _line_history(gateway: str | None, since: int, now: int, step: int) -> dict:
    """Latenza e perdita nel tempo, disponibilità del periodo e disservizi (eventi wan_down/wan_up)."""
    with connect() as db:
        rows = db.execute(
            "SELECT ts, online, delay_ms, loss_pct FROM line_samples WHERE gateway = ? AND ts >= ? ORDER BY ts",
            (gateway, since),
        ).fetchall()
        events = db.execute(
            """SELECT ts, kind, name, info FROM events WHERE kind IN ('wan_down', 'wan_up') AND ts >= ?
               ORDER BY ts""",
            (since - 30 * 86400,),     # un disservizio iniziato prima del periodo resta visibile
        ).fetchall()
    acc: dict[int, list[list[float]]] = defaultdict(lambda: [[], []])
    for r in rows:
        b = (r["ts"] - since) // step * step + since
        if r["delay_ms"] is not None:
            acc[b][0].append(r["delay_ms"])
        if r["loss_pct"] is not None:
            acc[b][1].append(r["loss_pct"])
    quality = [
        {"ts": b, "delay_ms": round(sum(d) / len(d), 1) if (d := acc[b][0]) else None,
         "loss_pct": round(max(lo), 1) if (lo := acc[b][1]) else None}
        for b in range(since, now + 1, step)
    ]
    outages, open_down = [], {}
    for e in events:
        if e["kind"] == "wan_down":
            open_down[e["name"]] = e
        elif e["name"] in open_down:
            start = open_down.pop(e["name"])["ts"]
            if e["ts"] >= since:
                outages.append({"gateway": e["name"], "start": start, "end": e["ts"], "duration": e["ts"] - start})
    for name, e in open_down.items():   # ancora in corso
        outages.append({"gateway": name, "start": e["ts"], "end": None, "duration": now - e["ts"]})
    return {
        "quality": quality,
        "availability": round(100 * sum(r["online"] for r in rows) / len(rows), 2) if rows else None,
        "outages": sorted(outages, key=lambda o: o["start"], reverse=True)[:20],
    }
