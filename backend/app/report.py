"""Report del periodo (di solito la settimana): disponibilità, traffico, linea, dispositivi.

Lo stesso riepilogo si vede nella pagina Report e, se attivato, arriva ogni lunedì su Telegram.
"""
import html
import time
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends

from .core.config import get_settings
from .core.db import connect
from .core.security import current_user
from .poller import INTERNET

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

WEAK_DBM = -75


def _deltas(rows) -> dict[str, list[int]]:
    """Somma degli incrementi dei contatori (in, out) per AP, saltando gli azzeramenti dei riavvii."""
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    prev: dict[tuple[str, str], tuple[int, int]] = {}
    for r in rows:
        key = (r["ap"], r["iface"])
        p = prev.get(key)
        prev[key] = (r["in_bytes"], r["out_bytes"])
        if not p:
            continue
        d_in, d_out = r["in_bytes"] - p[0], r["out_bytes"] - p[1]
        if d_in >= 0 and d_out >= 0:
            out[r["ap"]][0] += d_in
            out[r["ap"]][1] += d_out
    return out


def build(days: float = 7) -> dict:
    days = max(1.0, min(days, 30.0))
    now = int(time.time())
    since = now - int(days * 86400)
    step = max(30, get_settings().poll_interval)
    with connect() as db:
        aps = [r["ap"] for r in db.execute("SELECT ap FROM ap_status ORDER BY ap")]
        presence = {r["ap"]: dict(r) for r in db.execute(
            """SELECT ap, COUNT(*) AS n, MIN(ts) AS first, MAX(in_bytes) AS peak, AVG(in_bytes) AS avg
               FROM samples WHERE iface = '_clients' AND ts >= ? GROUP BY ap""", (since,))}
        traffic = _deltas(db.execute(
            """SELECT ap, iface, in_bytes, out_bytes FROM samples
               WHERE ts >= ? AND iface LIKE 'wlan-%' AND ap <> ? ORDER BY ap, iface, ts""", (since, INTERNET)))
        wan = _deltas(db.execute(
            "SELECT ap, iface, in_bytes, out_bytes FROM samples WHERE ap = ? AND iface = 'wan' AND ts >= ? ORDER BY ts",
            (INTERNET, since)))
        signal = {r["ap"]: dict(r) for r in db.execute(
            f"""SELECT ap, AVG(rssi) AS avg, 100.0 * SUM(rssi < {WEAK_DBM}) / COUNT(*) AS weak
                FROM rssi_samples WHERE ts >= ? GROUP BY ap""", (since,))}
        kinds = Counter()
        down_per_ap: Counter[str] = Counter()
        for r in db.execute("SELECT kind, ap FROM events WHERE ts >= ?", (since,)):
            kinds[r["kind"]] += 1
            if r["kind"] == "ap_down":
                down_per_ap[r["ap"]] += 1
        line = db.execute(
            """SELECT COUNT(*) AS n, SUM(online) AS up, AVG(delay_ms) AS delay, MAX(loss_pct) AS loss
               FROM line_samples WHERE ts >= ?""", (since,)).fetchone()
        new = [dict(r) for r in db.execute(
            """SELECT d.mac, COALESCE(a.name, d.hostname, d.last_ip, d.mac) AS name, d.first_seen, d.last_ap, d.known
               FROM devices d LEFT JOIN aliases a ON a.mac = d.mac WHERE d.first_seen >= ?
               ORDER BY d.first_seen DESC LIMIT 30""", (since,))]
        busiest = [dict(r) for r in db.execute(
            """SELECT s.mac, COALESCE(a.name, d.hostname, d.last_ip, s.mac) AS name, COUNT(*) AS n,
                      AVG(s.rssi) AS rssi
               FROM rssi_samples s LEFT JOIN aliases a ON a.mac = s.mac LEFT JOIN devices d ON d.mac = s.mac
               WHERE s.ts >= ? GROUP BY s.mac ORDER BY n DESC LIMIT 10""", (since,))]
        roams = Counter(r["mac"] for r in db.execute(
            "SELECT mac FROM events WHERE kind = 'roam' AND ts >= ?", (since,)))

    ap_rows = []
    for ap in aps:
        p = presence.get(ap)
        start = max(since, p["first"]) if p else since
        expected = max(1, (now - start) // step)
        s = signal.get(ap) or {}
        down, up = (traffic.get(ap) or [0, 0])[1], (traffic.get(ap) or [0, 0])[0]
        ap_rows.append({
            "ap": ap,
            "availability": round(min(100.0, 100 * p["n"] / expected), 1) if p else 0.0,
            "peak_clients": p["peak"] if p else 0,
            "avg_clients": round(p["avg"], 1) if p and p["avg"] is not None else 0,
            "down": down, "up": up,
            "rssi": round(s["avg"]) if s.get("avg") is not None else None,
            "weak_pct": round(s["weak"]) if s.get("weak") is not None else None,
            "outages": down_per_ap.get(ap, 0),
        })
    w = wan.get(INTERNET) or [0, 0]
    bounce = max(4, round(6 * days))
    return {
        "since": since, "until": now, "days": days,
        "aps": ap_rows,
        "wifi": {"down": sum(a["down"] for a in ap_rows), "up": sum(a["up"] for a in ap_rows)},
        "internet": {
            "available": bool(line and line["n"]),
            "availability": round(100 * line["up"] / line["n"], 2) if line and line["n"] else None,
            "delay_ms": round(line["delay"], 1) if line and line["delay"] is not None else None,
            "max_loss": line["loss"] if line else None,
            "outages": kinds.get("wan_down", 0), "down": w[0], "up": w[1],
        },
        "events": dict(kinds),
        "new_devices": new,
        "busiest": [{"mac": b["mac"], "name": b["name"], "hours": round(b["n"] * step / 3600, 1),
                     "rssi": round(b["rssi"]) if b["rssi"] is not None else None} for b in busiest],
        "bouncing": [m for m, n in roams.items() if n >= bounce],
    }


def _gb(n: int) -> str:
    return f"{n / 1e9:.1f} GB"


def as_text(r: dict) -> str:
    """Riepilogo compatto per Telegram (HTML semplice)."""
    lines = [f"<b>Zyxel Monitor — ultimi {r['days']:g} giorni</b>", ""]
    for a in r["aps"]:
        extra = f", {a['outages']} cadute" if a["outages"] else ""
        lines.append(f"• <b>{html.escape(a['ap'])}</b>: {a['availability']}% online, picco {a['peak_clients']} client, "
                     f"{_gb(a['down'] + a['up'])}{extra}")
    i = r["internet"]
    if i["available"]:
        lines += ["", f"Internet: {i['availability']}% disponibile, {i['outages']} disservizi, "
                      f"latenza media {i['delay_ms']} ms, {_gb(i['down'])} scaricati"]
    lines.append(f"Wi-Fi: {_gb(r['wifi']['down'])} scaricati, {_gb(r['wifi']['up'])} inviati")
    if r["new_devices"]:
        names = ", ".join(html.escape(d["name"]) for d in r["new_devices"][:8])
        lines.append(f"Dispositivi nuovi: {len(r['new_devices'])} ({names})")
    if r["bouncing"]:
        lines.append(f"Dispositivi che rimbalzano fra gli AP: {len(r['bouncing'])}")
    return "\n".join(lines)


@router.get("/report")
def report(days: float = 7):
    return build(days)
