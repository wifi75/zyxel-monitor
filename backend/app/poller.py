"""Ciclo di raccolta: interroga tutti gli AP, aggiorna stato, client, eventi e campioni."""
import asyncio
import json
import logging
import time

import ipaddress

from .collectors import names, opnsense, snmp, ssh
from .collectors.base import ApReading
from .core.config import AccessPoint, get_settings
from .core.db import connect

log = logging.getLogger("poller")


async def read_ap(ap: AccessPoint) -> ApReading:
    s = get_settings()
    if ap.method == "snmp":
        return await snmp.collect(ap.host, s.snmp_community)
    return await ssh.collect(ap.host, s.ssh_user, s.ssh_password)


async def poll_once() -> None:
    get_settings.cache_clear()   # rilegge il .env: una password corretta vale senza riavvio
    aps = get_settings().access_points()
    readings = await asyncio.gather(*(read_ap(ap) for ap in aps))
    now = int(time.time())

    arp = await names.arp_table()
    leases: dict[str, tuple[str, str | None]] = {}
    if opnsense.enabled():
        try:
            leases = await opnsense.leases()
        except Exception as exc:
            log.warning("OPNsense lease non disponibili: %s", exc)
    # completa gli IP mancanti (SNMP non li fornisce): prima DHCP di OPNsense, poi ARP
    for r in readings:
        for c in r.clients:
            c.ip = c.ip or (leases.get(c.mac) or (None,))[0] or arp.get(c.mac)
    all_clients = [(ap, c) for ap, r in zip(aps, readings, strict=True) for c in r.clients]
    dns_names = await asyncio.gather(*(names.hostname(c.ip) for _, c in all_clients))
    # il nome dato dal DHCP (quello che il dispositivo dichiara) vale più del DNS inverso
    hostnames = [
        (leases.get(c.mac) or (None, None))[1] or dns_name
        for (_, c), dns_name in zip(all_clients, dns_names, strict=True)
    ]
    if opnsense.enabled():
        await store_dns(leases)
        await store_internet(now)

    with connect() as db:
        aliases = {row["mac"]: row["name"] for row in db.execute("SELECT mac, name FROM aliases")}
        prev_status = {row["ap"]: row["online"] for row in db.execute("SELECT ap, online FROM ap_status")}
        prev_clients = {row["mac"]: dict(row) for row in db.execute("SELECT * FROM clients")}

        # --- stato AP ---
        for ap, r in zip(aps, readings, strict=True):
            was = prev_status.get(ap.name)
            if was is not None and bool(was) != r.online:
                db.execute(
                    "INSERT INTO events(ts, kind, ap, info) VALUES (?,?,?,?)",
                    (now, "ap_up" if r.online else "ap_down", ap.name, r.error),
                )
            db.execute(
                """INSERT INTO ap_status(ap, host, method, online, model, firmware, uptime_s, clients,
                                         radios, error, last_seen, updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(ap) DO UPDATE SET
                     host=excluded.host, method=excluded.method, online=excluded.online,
                     model=COALESCE(excluded.model, ap_status.model),
                     firmware=COALESCE(excluded.firmware, ap_status.firmware),
                     uptime_s=excluded.uptime_s, clients=excluded.clients, radios=excluded.radios,
                     error=excluded.error,
                     last_seen=COALESCE(excluded.last_seen, ap_status.last_seen),
                     updated=excluded.updated""",
                (
                    ap.name, ap.host, ap.method, int(r.online), r.model, r.firmware, r.uptime_s,
                    len(r.clients) if r.online else None,
                    json.dumps([vars(x) for x in r.radios]), r.error,
                    now if r.online else None, now,
                ),
            )
            if r.online:
                db.execute(
                    "INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,NULL)",
                    (now, ap.name, "_clients", len(r.clients)),
                )
                db.executemany(
                    "INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,?)",
                    [(now, ap.name, iface, rx, tx) for iface, (rx, tx) in r.traffic.items()],
                )

        # --- client ed eventi ---
        # i client di un AP non raggiungibile restano come erano: niente false disconnessioni
        offline_aps = {ap.name for ap, r in zip(aps, readings, strict=True) if not r.online}
        current: dict[str, dict] = {
            mac: row for mac, row in prev_clients.items() if row["ap"] in offline_aps
        }
        for (ap, c), host in zip(all_clients, hostnames, strict=True):
            current[c.mac] = {
                "mac": c.mac, "ap": ap.name, "ip": c.ip, "hostname": host, "ssid": c.ssid,
                "band": c.band, "rssi_dbm": c.rssi_dbm, "tx_rate": c.tx_rate, "rx_rate": c.rx_rate,
                "capability": c.capability, "connected_at": c.connected_at, "updated": now,
            }

        def label(row: dict) -> str:
            return aliases.get(row["mac"]) or row.get("hostname") or row.get("ip") or row["mac"]

        events = []
        for mac, row in current.items():
            old = prev_clients.get(mac)
            if old is None:
                events.append((now, "connect", mac, label(row), row["ap"], row["band"]))
            elif old["ap"] != row["ap"]:
                events.append((now, "roam", mac, label(row), row["ap"], f"da {old['ap']}"))
        for mac, old in prev_clients.items():
            if mac not in current:
                events.append((now, "disconnect", mac, label(old), old["ap"], None))
        if prev_clients or prev_status:   # al primissimo avvio non registriamo "connessioni" finte
            db.executemany(
                "INSERT INTO events(ts, kind, mac, name, ap, info) VALUES (?,?,?,?,?,?)", events
            )

        db.execute("DELETE FROM clients")
        db.executemany(
            """INSERT INTO clients(mac, ap, ip, hostname, ssid, band, rssi_dbm, tx_rate, rx_rate,
                                   capability, connected_at, updated)
               VALUES (:mac,:ap,:ip,:hostname,:ssid,:band,:rssi_dbm,:tx_rate,:rx_rate,
                       :capability,:connected_at,:updated)""",
            list(current.values()),
        )

    log.info("ciclo completato: %d AP, %d client", len(aps), len(current))


# domini tecnici che non sono "siti visitati"
_SKIP_SUFFIX = (".in-addr.arpa", ".ip6.arpa", ".local", ".lan", ".home.arpa")
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "edu", "ac"}


def site_of(domain: str, local_domain: str) -> str | None:
    d = domain.strip().rstrip(".").lower()
    if not d or "." not in d or d.endswith(_SKIP_SUFFIX):
        return None
    if local_domain and (d == local_domain or d.endswith("." + local_domain)):
        return None
    parts = d.split(".")
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) == 2:
        return ".".join(parts[-3:])      # es. bbc.co.uk
    return ".".join(parts[-2:])


async def store_dns(leases: dict[str, tuple[str, str | None]]) -> None:
    """Salva le nuove query DNS di OPNsense (solo quelle successive all'ultima già salvata)."""
    try:
        rows = await opnsense.dns_queries()
    except Exception as exc:
        log.warning("OPNsense DNS non disponibile: %s", exc)
        return
    local = get_settings().local_domain
    by_name = {h.split(".")[0].lower(): ip for ip, h in leases.values() if h}
    with connect() as db:
        last = db.execute("SELECT COALESCE(MAX(ts), 0) FROM dns").fetchone()[0]
        batch = []
        for r in rows:
            if r["time"] <= last or r["action"].lower() != "pass":
                continue
            site = site_of(r["domain"], local)
            client = r["client"]
            try:
                ipaddress.ip_address(client)
            except ValueError:   # OPNsense a volte mostra il nome al posto dell'IP
                client = by_name.get(client.split(".")[0].lower(), client)
            if site:
                batch.append((r["time"], client, site))
        db.executemany("INSERT INTO dns(ts, client_ip, site) VALUES (?,?,?)", batch)


# ultimo stato letto da OPNsense (linea, DNS): servito direttamente dall'API
internet_state: dict = {}


async def store_internet(now: int) -> None:
    """Stato della linea e contatori WAN (salvati come campioni dell'AP fittizio "_internet")."""
    try:
        gws, wan, dns = await asyncio.gather(
            opnsense.gateways(), opnsense.interface_bytes(get_settings().opnsense_wan_if), opnsense.dns_totals()
        )
    except Exception as exc:
        log.warning("OPNsense stato linea non disponibile: %s", exc)
        return
    internet_state.update({"gateways": gws, "dns": dns, "updated": now})
    if wan:
        with connect() as db:
            db.execute(
                "INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,?)",
                (now, INTERNET, "wan", wan[0], wan[1]),
            )


INTERNET = "_internet"


def prune() -> None:
    cutoff = int(time.time()) - get_settings().retention_days * 86400
    with connect() as db:
        db.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
        db.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        db.execute("DELETE FROM dns WHERE ts < ?", (cutoff,))


async def run_forever() -> None:
    interval = get_settings().poll_interval
    last_prune = 0.0
    while True:
        started = time.monotonic()
        try:
            await poll_once()
            if time.time() - last_prune > 3600:
                prune()
                last_prune = time.time()
        except Exception:
            log.exception("errore nel ciclo di raccolta")
        await asyncio.sleep(max(5, interval - (time.monotonic() - started)))
