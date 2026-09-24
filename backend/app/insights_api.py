"""Analisi: dispositivi nuovi, qualità del segnale, roaming, consumo per dispositivo, disposizione dashboard."""
import json
import time
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .collectors import opnsense
from .core.db import connect
from .core.security import current_user
from .devices import device_type

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

WEAK_DBM = -75


def _since(hours: float) -> tuple[float, int]:
    hours = max(0.25, min(hours, 24 * 30))
    return hours, int(time.time() - hours * 3600)


def _labels(db) -> dict[str, str]:
    """mac → nome da mostrare: alias > nome DHCP/DNS > IP."""
    names = {r["mac"]: r["hostname"] or r["last_ip"] for r in db.execute("SELECT mac, hostname, last_ip FROM devices")}
    names.update({r["mac"]: r["name"] for r in db.execute("SELECT mac, name FROM aliases")})
    return names


# ---------- dispositivi ----------
@router.get("/devices")
def list_devices():
    with connect() as db:
        rows = db.execute(
            """SELECT d.*, a.name AS alias, c.ap AS online_ap, c.rssi_dbm FROM devices d
               LEFT JOIN aliases a ON a.mac = d.mac LEFT JOIN clients c ON c.mac = d.mac
               ORDER BY d.known, d.last_seen DESC"""
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["known"] = bool(d["known"])
        d["online"] = d.pop("online_ap") is not None
        d["device_type"] = device_type(d["alias"] or d["hostname"], d["mac"])
        out.append(d)
    return out


class KnownIn(BaseModel):
    known: bool


@router.put("/devices/{mac}/known")
def set_known(mac: str, body: KnownIn):
    with connect() as db:
        cur = db.execute("UPDATE devices SET known = ? WHERE mac = ?", (int(body.known), mac.lower()))
    if not cur.rowcount:
        raise HTTPException(404, "Dispositivo non trovato")
    return {"ok": True}


@router.post("/devices/known-all")
def set_all_known():
    with connect() as db:
        n = db.execute("UPDATE devices SET known = 1 WHERE known = 0").rowcount
    return {"ok": True, "updated": n}


@router.delete("/devices/{mac}")
def forget_device(mac: str):
    """Toglie un dispositivo dall'elenco: se torna, risulterà di nuovo nuovo."""
    with connect() as db:
        db.execute("DELETE FROM devices WHERE mac = ?", (mac.lower(),))
    return {"ok": True}


# ---------- segnale ----------
@router.get("/signal")
def signal_history(mac: str, hours: float = 24, points: int = 120):
    """Segnale medio e minimo di un dispositivo nel tempo, in bucket."""
    hours, since = _since(hours)
    points = max(10, min(points, 500))
    step = max(60, int(hours * 3600 / points))
    with connect() as db:
        rows = db.execute(
            "SELECT ts, ap, rssi FROM rssi_samples WHERE mac = ? AND ts >= ? ORDER BY ts", (mac.lower(), since)
        ).fetchall()
    buckets: dict[int, list[int]] = defaultdict(list)
    aps: dict[int, str] = {}
    for r in rows:
        b = (r["ts"] - since) // step * step + since
        buckets[b].append(r["rssi"])
        aps[b] = r["ap"]
    out = []
    for b in range(since, int(time.time()) + 1, step):
        v = buckets.get(b)
        out.append({"ts": b, "avg": round(sum(v) / len(v)) if v else None, "min": min(v) if v else None,
                    "ap": aps.get(b)})
    return {"step": step, "points": out}


@router.get("/signal/aps")
def signal_by_ap(hours: float = 24, ap: str | None = None):
    """Per ogni AP: segnale medio e quota di letture deboli; dispositivi col segnale peggiore."""
    hours, since = _since(hours)
    with connect() as db:
        per_ap = db.execute(
            f"""SELECT ap, AVG(rssi) AS avg, SUM(rssi < {WEAK_DBM}) AS weak, COUNT(*) AS n,
                       COUNT(DISTINCT mac) AS devices
                FROM rssi_samples WHERE ts >= ? AND (? IS NULL OR ap = ?) GROUP BY ap ORDER BY avg""",
            (since, ap, ap),
        ).fetchall()
        worst = db.execute(
            """SELECT mac, AVG(rssi) AS avg, MIN(rssi) AS min, COUNT(*) AS n FROM rssi_samples
               WHERE ts >= ? AND (? IS NULL OR ap = ?) GROUP BY mac HAVING n >= 3 ORDER BY avg LIMIT 8""",
            (since, ap, ap),
        ).fetchall()
        last_ap = {r["mac"]: r["last_ap"] for r in db.execute("SELECT mac, last_ap FROM devices")}
        names = _labels(db)
    return {
        "weak_dbm": WEAK_DBM,
        "aps": [{"ap": r["ap"], "avg": round(r["avg"]), "weak_pct": round(100 * r["weak"] / r["n"]),
                 "devices": r["devices"]} for r in per_ap],
        "worst": [{"mac": r["mac"], "name": names.get(r["mac"]) or r["mac"], "ap": last_ap.get(r["mac"]),
                   "avg": round(r["avg"]), "min": r["min"]} for r in worst],
    }


# ---------- roaming ----------
@router.get("/roaming")
def roaming(hours: float = 24, ap: str | None = None):
    """Spostamenti fra AP (eventi "roam") e dispositivi che rimbalzano di continuo."""
    hours, since = _since(hours)
    with connect() as db:
        rows = db.execute(
            "SELECT mac, name, ap, info FROM events WHERE kind = 'roam' AND ts >= ?", (since,)
        ).fetchall()
    pairs: Counter[tuple[str, str]] = Counter()
    per_dev: Counter[str] = Counter()
    dev_name: dict[str, str] = {}
    dev_aps: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        src = (r["info"] or "")[3:] if (r["info"] or "").startswith("da ") else "?"
        if ap and ap not in (src, r["ap"]):
            continue
        pairs[(src, r["ap"])] += 1
        per_dev[r["mac"]] += 1
        dev_name[r["mac"]] = r["name"] or r["mac"]
        dev_aps[r["mac"]].update((src, r["ap"]))
    # un dispositivo che cambia AP più di ~6 volte al giorno sta "rimbalzando": potenze radio da rivedere
    threshold = max(4, round(6 * hours / 24))
    return {
        "threshold": threshold,
        "pairs": [{"from": a, "to": b, "count": n} for (a, b), n in pairs.most_common(12)],
        "devices": [{"mac": m, "name": dev_name[m], "count": n, "aps": sorted(dev_aps[m] - {"?"}),
                     "bouncing": n >= threshold} for m, n in per_dev.most_common(10)],
    }


# ---------- consumo per dispositivo (NetFlow di OPNsense) ----------
_usage_cache: dict[float, tuple[float, dict]] = {}


@router.get("/usage/devices")
async def usage_devices(hours: float = 24):
    hours, since = _since(hours)
    if not opnsense.enabled():
        return {"available": False, "reason": "opnsense"}
    hit = _usage_cache.get(hours)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    try:
        if not await opnsense.netflow_active():
            return {"available": False, "reason": "netflow"}
        per_ip, raw = await opnsense.bytes_per_address(since, int(time.time()))
    except Exception as exc:
        return {"available": False, "reason": "error", "message": str(exc)}
    with connect() as db:
        rows = db.execute("SELECT mac, last_ip, hostname FROM devices").fetchall()
        by_ip = {r["last_ip"]: r["mac"] for r in rows if r["last_ip"]}
        hostnames = {r["mac"]: r["hostname"] for r in rows}
        names = _labels(db)
    items = []
    by_type: Counter[str] = Counter()
    for ip, n in per_ip.items():
        mac = by_ip.get(ip)
        if not mac or n <= 0:
            continue
        kind = device_type(names.get(mac) or hostnames.get(mac), mac)
        items.append({"mac": mac, "ip": ip, "name": names.get(mac) or ip, "device_type": kind, "bytes": n})
        by_type[kind] += n
    items.sort(key=lambda i: i["bytes"], reverse=True)
    result = {
        "available": True, "items": items[:15],
        "by_type": [{"type": k, "bytes": v} for k, v in by_type.most_common()],
        # quando non si riconosce nulla, il pannello mostra cosa ha risposto OPNsense
        "debug": None if items else {**raw, "addresses": len(per_ip), "sample_addresses": sorted(per_ip)[:10]},
    }
    if items:   # un risultato vuoto non si tiene in cache: i dati di Insight possono arrivare da un momento all'altro
        _usage_cache[hours] = (time.time(), result)
    return result


# ---------- disposizione della dashboard (per utente) ----------
class Widget(BaseModel):
    i: str = Field(max_length=40)
    x: int = Field(ge=0, le=48)
    y: int = Field(ge=0, le=1000)
    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=60)


class LayoutIn(BaseModel):
    overview: list[Widget] | None = Field(None, max_length=40)
    ap: list[Widget] | None = Field(None, max_length=40)


@router.get("/layout")
def get_layout(user: str = Depends(current_user)):
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (f"layout:{user}",)).fetchone()
    return json.loads(row["value"]) if row else {}


@router.put("/layout")
def save_layout(body: LayoutIn, user: str = Depends(current_user)):
    """Salva solo le viste inviate: la disposizione della panoramica non tocca quella degli AP."""
    layout = {**get_layout(user), **body.model_dump(exclude_none=True)}
    with connect() as db:
        db.execute(
            "INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (f"layout:{user}", json.dumps(layout)),
        )
    return {"ok": True}


@router.delete("/layout")
def reset_layout(user: str = Depends(current_user)):
    with connect() as db:
        db.execute("DELETE FROM settings WHERE key = ?", (f"layout:{user}",))
    return {"ok": True}
