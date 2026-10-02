"""Analisi: dispositivi nuovi, qualità del segnale, roaming, consumo per dispositivo, disposizione dashboard."""
import asyncio
import logging
import ipaddress
import json
import time
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .collectors import names as names_mod
from .collectors import opnsense
from .core.db import connect
from .core.security import current_user
from .devices import device_type
from .oui import vendor

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
log = logging.getLogger("insights")

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
        # qualità nelle ultime 24 ore: scollegamenti e spostamenti fra AP
        since = int(time.time()) - 86400
        counts = {kind: dict(db.execute(
            "SELECT mac, COUNT(*) FROM events WHERE kind = ? AND ts >= ? GROUP BY mac", (kind, since)).fetchall())
            for kind in ("disconnect", "roam")}
    out = []
    for r in rows:
        d = dict(r)
        d["known"] = bool(d["known"])
        d["critical"] = bool(d.get("critical"))
        d["drops_24h"] = counts["disconnect"].get(d["mac"], 0)
        d["roams_24h"] = counts["roam"].get(d["mac"], 0)
        d["online"] = d.pop("online_ap") is not None
        d["device_type"] = device_type(d["alias"] or d["hostname"], d["mac"])
        d["vendor"] = vendor(d["mac"])
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


class CriticalIn(BaseModel):
    critical: bool


@router.put("/devices/{mac}/critical")
def set_critical(mac: str, body: CriticalIn):
    """Dispositivo importante (inverter, cancello...): avviso su Telegram se resta scollegato."""
    with connect() as db:
        cur = db.execute("UPDATE devices SET critical = ? WHERE mac = ?", (int(body.critical), mac.lower()))
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


def _is_lan(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_private and not a.is_multicast and not a.is_loopback


@router.get("/usage/devices")
async def usage_devices(hours: float = 24):
    hours, since = _since(hours)
    if not opnsense.enabled():
        return {"available": False, "reason": "opnsense"}
    hit = _usage_cache.get(hours)
    if hit and time.time() - hit[0] < 1800:     # Insight ha totali giornalieri: inutile riscaricarli spesso
        return hit[1]
    try:
        if not await opnsense.netflow_active():
            return {"available": False, "reason": "netflow"}
        split: dict[str, list[int]] = {}
        try:
            split = await opnsense.traffic_per_address(since, int(time.time()))
        except Exception as exc:        # esportazione non disponibile: si resta ai soli byte inviati
            log.warning("Insight export non disponibile: %s", exc)
        if split:
            per_ip = {ip: d + u for ip, (d, u) in split.items()}
            raw = {"path": "export", "rows": len(split), "sample": ""}
        else:
            per_ip, raw = await opnsense.bytes_per_address(since, int(time.time()))
    except Exception as exc:
        return {"available": False, "reason": "error", "message": str(exc)}
    with connect() as db:
        rows = db.execute("SELECT mac, last_ip, hostname FROM devices").fetchall()
        by_ip = {r["last_ip"]: r["mac"] for r in rows if r["last_ip"]}
        hostnames = {r["mac"]: r["hostname"] for r in rows}
        names = _labels(db)
    # si contano solo gli indirizzi della rete di casa: gli IP pubblici sono i server remoti, il multicast è servizio.
    # I dispositivi via cavo non passano dagli AP: nome dal DNS inverso, altrimenti l'IP.
    lan = [(ip, n) for ip, n in per_ip.items() if n > 0 and _is_lan(ip)]
    wired = dict(zip([ip for ip, _ in lan if ip not in by_ip],
                     await asyncio.gather(*(names_mod.hostname(ip) for ip, _ in lan if ip not in by_ip)), strict=True))
    items = []
    by_type: Counter[str] = Counter()
    for ip, n in lan:
        mac = by_ip.get(ip)
        if mac:
            label = names.get(mac) or ip
            kind = device_type(names.get(mac) or hostnames.get(mac), mac)
        else:
            label = wired.get(ip) or ip
            kind = "Via cavo"
        down, up = split.get(ip, [None, None])
        items.append({"mac": mac, "ip": ip, "name": label, "device_type": kind, "bytes": n, "down": down, "up": up})
        by_type[kind] += n
    items.sort(key=lambda i: i["bytes"], reverse=True)
    result = {
        "available": True, "items": items[:15], "both_ways": bool(split),
        "by_type": [{"type": k, "bytes": v} for k, v in by_type.most_common()],
        # quando non si riconosce nulla, il pannello mostra cosa ha risposto OPNsense
        "debug": None if items else {**raw, "addresses": len(per_ip), "sample_addresses": sorted(per_ip)[:10]},
    }
    if items:   # un risultato vuoto non si tiene in cache: i dati di Insight possono arrivare da un momento all'altro
        _usage_cache[hours] = (time.time(), result)
    return result


_apps_cache: dict[float, tuple[float, dict]] = {}


@router.get("/usage/apps")
async def usage_apps(hours: float = 24):
    """Traffico della casa per servizio (YouTube, Netflix, Microsoft…), dagli indirizzi remoti di NetFlow."""
    from . import services
    hours, since = _since(hours)
    if not opnsense.enabled():
        return {"available": False, "reason": "opnsense"}
    hit = _apps_cache.get(hours)
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    try:
        if not await opnsense.netflow_active():
            return {"available": False, "reason": "netflow"}
        per_remote = opnsense.remote_traffic(await opnsense.insight_rows(since, int(time.time())))
    except Exception as exc:
        return {"available": False, "reason": "error", "message": str(exc)}
    items = await services.group(per_remote)
    result = {"available": True, "items": items[:12], "total": sum(i["bytes"] for i in items)}
    if items:
        _apps_cache[hours] = (time.time(), result)
    return result


@router.get("/clients/wired")
async def clients_wired():
    """Dispositivi via cavo: nella tabella ARP di OPNsense ma non collegati a un AP (né AP essi stessi)."""
    from .core import store
    with connect() as db:
        wifi = {r["mac"] for r in db.execute("SELECT mac FROM clients")}
        # visti almeno una volta su un AP: un telefono appena uscito resta nella tabella ARP per una ventina di
        # minuti e non va contato come cablato
        ever_wifi = {r["mac"] for r in db.execute("SELECT mac FROM devices")}
        names = _labels(db)
    if not opnsense.enabled():
        return {"available": False, "reason": "opnsense", "wireless": len(wifi), "wired": None, "items": []}
    try:
        rows = await opnsense.arp()
        try:
            lease_names = {m: h for m, (_ip, h) in (await opnsense.leases()).items() if h}
        except Exception:               # senza Kea si va avanti coi nomi del pannello e il DNS inverso
            lease_names = {}
    except Exception as exc:
        return {"available": False, "reason": "error", "message": str(exc), "wireless": len(wifi), "wired": None,
                "items": []}
    ap_hosts = {a.host for a in store.list_aps()}
    # OPNsense ha più reti (WAN, VLAN, server): si tiene solo l'interfaccia su cui stanno gli AP
    ap_intfs = {str(r.get("intf") or "") for r in rows if str(r.get("ip") or "") in ap_hosts} - {""}
    items, seen = [], set()
    for r in rows:
        mac = str(r.get("mac") or "").lower()
        ip = str(r.get("ip") or "")
        if not mac or mac in seen or mac in wifi or mac in ever_wifi or ip in ap_hosts or not _is_lan(ip):
            continue
        if ap_intfs and str(r.get("intf") or "") not in ap_intfs:
            continue
        if r.get("permanent") in (True, 1, "1", "true") or "incomplete" in mac:
            continue                       # indirizzi dell'OPNsense stesso, voci non risolte
        if r.get("expired") in (True, 1, "1", "true"):
            continue
        seen.add(mac)
        items.append({"mac": mac, "ip": ip, "name": names.get(mac) or lease_names.get(mac) or r.get("hostname"),
                      "vendor": vendor(mac), "intf": r.get("intf_description") or r.get("intf")})
    # chi non ha un nome nel pannello né nel DHCP: DNS inverso, così ogni riga dice cos'è
    unnamed = [i for i in items if not i["name"]]
    for i, host in zip(unnamed, await asyncio.gather(*(names_mod.hostname(i["ip"]) for i in unnamed)), strict=True):
        i["name"] = host
    items.sort(key=lambda i: tuple(int(p) for p in i["ip"].split(".")) if i["ip"].count(".") == 3 else (999,))
    return {"available": True, "wireless": len(wifi), "wired": len(items), "items": items}


# ---------- stato del sistema ----------
@router.get("/system")
def system_status():
    """Salute del pannello: ultima lettura di ogni AP, database, ultimo backup."""
    from pathlib import Path

    from . import backup
    from .core.config import get_settings
    from .core.version import APP_VERSION
    now = int(time.time())
    step = get_settings().poll_interval
    with connect() as db:
        aps = [{"ap": r["ap"], "online": bool(r["online"]), "last_seen": r["last_seen"], "error": r["error"],
                "stale": bool(r["last_seen"] is None or now - r["last_seen"] > max(600, step * 5))}
               for r in db.execute("SELECT ap, online, last_seen, error FROM ap_status ORDER BY ap")]
        counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("events", "samples", "rssi_samples", "dns", "devices")}
    db_file = Path(get_settings().db_path)
    status = backup.status()
    return {"version": APP_VERSION, "now": now, "poll_interval": step, "aps": aps,
            "db_size": db_file.stat().st_size if db_file.exists() else None, "rows": counts,
            "last_backup": status["files"][0] if status["files"] else None}


# ---------- distacchi per ora del giorno ----------
@router.get("/drops/heatmap")
def drops_heatmap(days: float = 7):
    """Scollegamenti per AP e ora del giorno (0-23): mostra quando e dove la rete dà problemi."""
    days = max(1.0, min(days, 30.0))
    since = int(time.time() - days * 86400)
    import datetime as dt
    grid: dict[str, list[int]] = defaultdict(lambda: [0] * 24)
    with connect() as db:
        for r in db.execute("SELECT ts, ap FROM events WHERE kind = 'disconnect' AND ts >= ?", (since,)):
            grid[r["ap"] or "?"][dt.datetime.fromtimestamp(r["ts"]).hour] += 1
    return {"days": days, "aps": {ap: hours for ap, hours in sorted(grid.items())},
            "max": max((max(h) for h in grid.values()), default=0)}


# ---------- disponibilità degli AP nel tempo ----------
@router.get("/availability")
def availability(hours: float = 48, slots: int = 96):
    """Per ogni AP, la quota di letture riuscite in ogni intervallo (1 = sempre online, 0 = mai)."""
    from .core.config import get_settings
    hours = max(1.0, min(hours, 24 * 14))
    slots = max(12, min(slots, 288))
    now = int(time.time())
    since = now - int(hours * 3600)
    width = (now - since) / slots
    expected = max(1.0, width / max(30, get_settings().poll_interval))
    with connect() as db:
        aps = [r["ap"] for r in db.execute("SELECT ap FROM ap_status ORDER BY ap")]
        first = {r["ap"]: r["t"] for r in db.execute(
            "SELECT ap, MIN(ts) AS t FROM samples WHERE iface = '_clients' GROUP BY ap")}
        hits: dict[str, list[int]] = {ap: [0] * slots for ap in aps}
        for r in db.execute("SELECT ts, ap FROM samples WHERE iface = '_clients' AND ts >= ?", (since,)):
            if r["ap"] in hits:
                hits[r["ap"]][min(slots - 1, int((r["ts"] - since) / width))] += 1
    out = {}
    for ap in aps:
        start = first.get(ap) or now
        out[ap] = [None if since + (i + 1) * width < start else round(min(1.0, n / expected), 2)
                   for i, n in enumerate(hits[ap])]
    return {"since": since, "until": now, "slots": slots, "aps": out}


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
