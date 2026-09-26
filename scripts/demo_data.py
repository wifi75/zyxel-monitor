"""Riempie un database con una casa inventata, per gli screenshot e le prove dell'interfaccia.

Nessun dato reale: nomi, indirizzi e MAC sono di fantasia (i prefissi MAC sono di produttori veri solo
per mostrare la colonna "Produttore"). Si usa insieme a ZM_DEMO=1, che ferma la lettura degli AP:

    cd backend
    DB_PATH=../demo/monitor.db python ../scripts/demo_data.py
    DB_PATH=../demo/monitor.db ZM_DEMO=1 uvicorn app.main:app --port 8000
"""
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import connect, init_db  # noqa: E402
from app.core.security import ensure_default_user  # noqa: E402

random.seed(7)
NOW = int(time.time())
DAY = 86400
STEP = 300          # un campione ogni 5 minuti

APS = [
    # nome, modello, firmware, ip, metodo, canale 2.4, occupazione media 2.4
    ("Living room", "NWA50AX PRO", "V7.12(ACGE.0)", "192.168.10.11", "ssh", 6, 24),
    ("Bedroom", "NWA50AX PRO", "V7.12(ACGE.0)", "192.168.10.12", "ssh", 11, 12),
    ("Garage", "WAC6103D-I", "V6.28(AAXH.3)", "192.168.10.13", "ssh", 1, 18),
    ("Garden", "NWA1123-AC-PRO", "V6.28(ABHD.3)", "192.168.10.14", "ssh", 1, 9),
]

# nome, prefisso MAC (produttore), banda, AP preferito, segnale medio
CLIENTS = [
    ("pixel-8", "da:a1:19", "5GHz", "Living room", -52), ("anna-iphone", "ce:5e:31", "5GHz", "Bedroom", -58),
    ("macbook-air", "f0:18:98", "5GHz", "Living room", -49), ("work-laptop", "3c:22:fb", "5GHz", "Bedroom", -61),
    ("ipad-kids", "a6:40:2f", "5GHz", "Living room", -63), ("living-tv", "70:2a:d5", "5GHz", "Living room", -55),
    ("echo-kitchen", "08:c2:24", "5GHz", "Living room", -59), ("chromecast", "f4:f5:d8", "5GHz", "Bedroom", -60),
    ("shelly-plug-kitchen", "e8:9f:6d", "2.4GHz", "Living room", -48),
    ("shelly-light-porch", "98:f4:ab", "2.4GHz", "Garden", -62),
    ("shelly-gate", "84:f3:eb", "2.4GHz", "Garden", -66), ("shelly-shutter-bath", "2c:f4:32", "2.4GHz", "Bedroom", -57),
    ("shellyem-meter", "c4:d8:d5", "2.4GHz", "Garage", -41), ("inverter-solar", "24:62:ab", "2.4GHz", "Garage", -45),
    ("esp32-battery-bms", "24:62:ab", "2.4GHz", "Garage", -39), ("esp32-weather", "3c:8a:1f", "2.4GHz", "Garden", -71),
    ("tuya-washer-plug", "38:a5:c9", "2.4GHz", "Garage", -47), ("tuya-dryer-plug", "e4:ae:e4", "2.4GHz", "Garage", -50),
    ("printer-office", "30:05:5c", "2.4GHz", "Bedroom", -64),
    ("robot-vacuum", "50:ec:50", "2.4GHz", "Living room", -69),
    ("heat-pump", "ca:2c:4f", "2.4GHz", "Garage", -52), ("doorbell-cam", "44:19:b6", "2.4GHz", "Garden", -73),
    ("sprinkler", "a4:cf:12", "2.4GHz", "Garden", -58), ("air-purifier", "78:1c:3c", "2.4GHz", "Bedroom", -54),
    ("smart-scale", "5c:cf:7f", "2.4GHz", "Bedroom", -60), ("3d-printer-plug", "e4:b3:23", "2.4GHz", "Garage", -40),
    ("nas-backup", "00:11:32", "5GHz", "Living room", -44), ("guest-phone", "7e:12:88", "2.4GHz", "Living room", -76),
]
NEW = {"guest-phone", "robot-vacuum"}
SITES = ["google.com", "youtube.com", "netflix.com", "whatsapp.net", "apple.com", "shelly.cloud", "amazon.com",
         "spotify.com", "wikipedia.org", "openweathermap.org", "github.com", "ntp.org"]


def mac(prefix: str, n: int) -> str:
    return f"{prefix}:{n // 256:02x}:{n % 256:02x}:{(n * 37) % 256:02x}"


def wave(t: int, base: float, amp: float) -> float:
    """Andamento giornaliero: più traffico la sera, poco di notte."""
    hour = (t % DAY) / 3600
    return max(0.0, base + amp * math.sin((hour - 13) / 24 * 2 * math.pi) + random.uniform(-amp, amp) * .25)


def main() -> None:
    init_db()
    ensure_default_user()
    with connect() as db:
        for table in ("access_points", "ap_status", "clients", "events", "samples", "dns", "aliases", "devices",
                      "rssi_samples", "line_samples", "site_config", "radio_policy"):
            db.execute(f"DELETE FROM {table}")
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('_seeded', '1')")
        # stesso intervallo dei campioni qui sotto: il report calcola la disponibilità su questo passo
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('poll_interval', ?)", (str(STEP),))

        by_ap: dict[str, list[tuple]] = {a[0]: [] for a in APS}
        clients = []
        for n, (name, prefix, band, ap, rssi) in enumerate(CLIENTS, start=1):
            m = mac(prefix, n)
            ip = f"192.168.10.{100 + n}"
            clients.append((m, ap, ip, name, band, rssi))
            by_ap[ap].append((band, rssi))
            first = NOW - (3600 * 5 if name in NEW else DAY * random.randint(3, 40))
            db.execute("INSERT INTO devices(mac, first_seen, last_seen, last_ap, last_ip, hostname, known, critical) "
                       "VALUES (?,?,?,?,?,?,?,?)",
                       (m, first, NOW, ap, ip, name, int(name not in NEW),
                        int(name in {"inverter-solar", "esp32-battery-bms", "shelly-gate"})))
            rate = 866 if band == "5GHz" else 72
            db.execute("INSERT INTO clients(mac, ap, ip, hostname, ssid, band, rssi_dbm, tx_rate, rx_rate, capability, "
                       "connected_at, updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (m, ap, ip, name, "HomeWiFi", band, rssi, rate, rate // 2,
                        "802.11ax" if band == "5GHz" else "802.11b/g/n", NOW - random.randint(600, DAY), NOW))
            for t in range(NOW - DAY, NOW, STEP):
                db.execute("INSERT INTO rssi_samples(ts, mac, ap, rssi) VALUES (?,?,?,?)",
                           (t, m, ap, rssi + random.randint(-4, 3)))
            for _ in range(random.randint(5, 60)):
                db.execute("INSERT INTO dns(ts, client_ip, site) VALUES (?,?,?)",
                           (NOW - random.randint(0, DAY), ip, random.choice(SITES)))
        db.execute("INSERT INTO aliases(mac, name) VALUES (?,?)", (clients[0][0], "Marco's phone"))

        for name, model, fw, ip, method, ch24, util in APS:
            n24 = sum(1 for b, _ in by_ap[name] if b == "2.4GHz")
            n5 = sum(1 for b, _ in by_ap[name] if b == "5GHz")
            db.execute("INSERT INTO access_points(name, host, method, ssh_user, ssh_password) VALUES (?,?,?,?,?)",
                       (name, ip, method, "admin", "demo-password"))
            radios = [{"band": "2.4GHz", "channel": ch24, "clients": n24, "tx_power": 20, "utilization": util,
                       "channel_auto": False},
                      {"band": "5GHz", "channel": {6: 36, 11: 52, 1: 100}[ch24] + (16 if name == "Garden" else 0),
                       "clients": n5, "tx_power": 23, "utilization": random.randint(1, 6), "channel_auto": False}]
            db.execute("INSERT INTO ap_status(ap, host, method, online, model, firmware, uptime_s, clients, radios, "
                       "error, last_seen, updated, cpu_pct, mem_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (name, ip, method, 1, model, fw, DAY * random.randint(2, 20) + 5000, n24 + n5,
                        json.dumps(radios), None, NOW, NOW, random.randint(3, 15), random.randint(35, 60)))
            rx = tx = 0
            for t in range(NOW - DAY, NOW + 1, STEP):
                down = wave(t, 1.6e6 if n5 else 3e5, 1.4e6 if n5 else 2e5)
                rx += int(down * STEP / 8 * .25)
                tx += int(down * STEP / 8)
                db.execute("INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,NULL)",
                           (t, name, "_clients", max(1, n24 + n5 + random.randint(-2, 1))))
                db.execute("INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,?)",
                           (t, name, "wlan-1-1", rx, tx))
                db.execute("INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,NULL)",
                           (t, name, "_util:2.4GHz", int(wave(t, util, util * .5))))

        wan_in = wan_out = 0
        for t in range(NOW - DAY, NOW + 1, STEP):
            down = wave(t, 8e6, 7e6)
            wan_in += int(down * STEP / 8)
            wan_out += int(down * STEP / 8 * .15)
            db.execute("INSERT INTO samples(ts, ap, iface, in_bytes, out_bytes) VALUES (?,?,?,?,?)",
                       (t, "_internet", "wan", wan_in, wan_out))
            db.execute("INSERT INTO line_samples(ts, gateway, online, delay_ms, loss_pct) VALUES (?,?,?,?,?)",
                       (t, "WAN_GW", 1, round(random.uniform(9, 16), 1), 0.0))

        kinds = ["connect", "disconnect", "roam"]
        for _ in range(120):
            name, _p, _b, ap, _r = random.choice(CLIENTS)
            m = next(c[0] for c in clients if c[3] == name)
            kind = random.choice(kinds)
            other = random.choice([a[0] for a in APS if a[0] != ap])
            db.execute("INSERT INTO events(ts, kind, mac, name, ap, info) VALUES (?,?,?,?,?,?)",
                       (NOW - random.randint(0, DAY), kind, m, name, ap, f"da {other}" if kind == "roam" else None))
        for name in NEW:
            m = next(c[0] for c in clients if c[3] == name)
            db.execute("INSERT INTO events(ts, kind, mac, name, ap, info) VALUES (?,?,?,?,?,?)",
                       (NOW - 5 * 3600, "new_device", m, name, "Living room", None))

        # stato della linea che il server tiene in memoria: in modalità dimostrativa lo legge da qui
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('_demo_internet', ?)", (json.dumps({
            "gateways": [{"name": "WAN_GW", "online": True, "down": False, "status": "Online", "delay": "12.4 ms",
                          "loss": "0.0 %", "monitor": "1.1.1.1"}],
            "dns": {"total": 48210, "blocked": 6130, "blocked_pct": 12.7, "since": NOW - 7 * DAY,
                    "top_blocked": [{"domain": d, "queries": q, "list": "ads"} for d, q in
                                    (("doubleclick.net", 812), ("app-measurement.com", 640), ("ads.youtube.com", 402),
                                     ("tracking.example", 233), ("metrics.tv-maker.com", 190))]},
            "updated": NOW}),))
    print("dati dimostrativi pronti")


if __name__ == "__main__":
    main()
