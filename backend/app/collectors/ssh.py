"""Lettura AP via SSH (CLI Zyxel) — per i modelli che in Nebula non attivano SNMP (NWA50AX PRO).

La CLI non accetta comandi passati in riga (`ssh host "cmd"` → "% session is not found"):
serve una shell interattiva a cui inviare i comandi.
"""
import asyncio
import datetime as dt
import re
import time

import asyncssh

from .base import ApReading, Client, Radio

# i contatori di traffico: "show interface ..." ha solo configurazione; candidati trovati con "show ?"
# (formato da verificare, l'ultimo output grezzo resta consultabile dal pannello: last_output)
COMMANDS = [
    "show version", "show system uptime", "show wireless-hal station info",
    "show wireless-hal statistic", "show port status", "show cpu status", "show mem status",
]
last_output: dict[str, tuple[float, str]] = {}


async def _shell(host: str, user: str, password: str, port: int = 22, timeout: float = 30) -> str:
    async with asyncssh.connect(
        host, port=port, username=user, password=password,
        known_hosts=None,            # AP in LAN, chiave che cambia al reset
        connect_timeout=10,
    ) as conn:
        proc = await conn.create_process(term_type="vt100", term_size=(200, 5000))
        proc.stdin.write("\n".join(COMMANDS) + "\nexit\n")
        chunks: list[str] = []

        async def reader():
            while True:
                data = await proc.stdout.read(65536)
                if not data:
                    break
                chunks.append(data)

        try:
            await asyncio.wait_for(reader(), timeout)
        except TimeoutError:
            pass
        proc.close()
        return "".join(chunks).replace("\r", "")


def _rate(value: str) -> int | None:
    m = re.match(r"(\d+)", value or "")
    return int(m.group(1)) if m else None


def parse_stations(text: str) -> list[Client]:
    clients: list[Client] = []
    cur: dict[str, str] | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("index:"):
            if cur:
                clients.append(_to_client(cur))
            cur = {}
        elif cur is not None and ":" in line and not line.endswith(">"):
            key, _, value = line.partition(":")
            cur[key.strip()] = value.strip()
        elif line.endswith(">"):   # prompt successivo: fine blocco
            if cur:
                clients.append(_to_client(cur))
            cur = None
    if cur:
        clients.append(_to_client(cur))
    return [c for c in clients if c.mac]


def _to_client(d: dict[str, str]) -> Client:
    ts = None
    if d.get("Time"):
        try:
            ts = int(dt.datetime.strptime(d["Time"], "%Y/%m/%d %H:%M:%S").timestamp())
        except ValueError:
            pass
    rssi = d.get("RSSI dBm", "")
    return Client(
        mac=d.get("MAC", "").lower(),
        ip=d.get("IPv4") or None,
        band=d.get("Band") or None,
        ssid=d.get("Display SSID") or d.get("SSID") or None,
        rssi_dbm=int(rssi) if re.fullmatch(r"-?\d+", rssi) else None,
        tx_rate=_rate(d.get("TxRate", "")),
        rx_rate=_rate(d.get("RxRate", "")),
        capability=d.get("Capability") or None,
        connected_at=ts,
    )


IFACE_START = re.compile(r"^\s*(?:(?:interface\s*)?name\s*[:=]\s*)?(eth\d+|wlan-\d+-\d+)\b", re.I)
# eco del comando: "Router> show interface wlan-1-1" apre il blocco di quell'interfaccia
SHOW_IFACE = re.compile(r"show interface (eth\d+|wlan-\d+-\d+)\b", re.I)
BYTES = re.compile(r"\b(rx|tx)[ _-]?(?:bytes|octets)\s*[:=]?\s*(\d+)", re.I)


def parse_traffic(text: str) -> dict[str, tuple[int, int]]:
    """Contatori (ricevuti, trasmessi) per interfaccia: accetta sia il formato "Name: wlan-1-1 … Rx bytes: N"
    sia quello di ifconfig ("wlan-1-1  Link encap … RX bytes:N … TX bytes:N")."""
    out: dict[str, tuple[int, int]] = {}
    cur: str | None = None
    rx = tx = None
    for line in text.splitlines():
        m = IFACE_START.match(line) or SHOW_IFACE.search(line)
        if m:
            if cur and rx is not None and tx is not None:
                out[cur] = (rx, tx)
            cur, rx, tx = m.group(1).lower(), None, None
        if cur:
            for kind, value in BYTES.findall(line):
                if kind.lower() == "rx":
                    rx = int(value)
                else:
                    tx = int(value)
    if cur and rx is not None and tx is not None:
        out[cur] = (rx, tx)
    return out


HAL_SLOT = re.compile(r"^\s*Slot:\s*(\d+)\s*$")
HAL_BYTES = re.compile(r"^\s*wlan(Received|Transmitted)Byte:\s*(\d+)")
HAL_RADIO = re.compile(r"^\s*(TxPower|Channel Utilization):\s*(\d+)")
# slot della radio → banda, come la riporta "show wireless-hal station info"
SLOT_BAND = {"1": "2.4GHz", "2": "5GHz", "3": "6GHz"}


def parse_hal_radios(text: str) -> dict[str, dict[str, int]]:
    """Potenza (dBm) e occupazione del canale (%) per banda da `show wireless-hal statistic`."""
    out: dict[str, dict[str, int]] = {}
    slot: str | None = None
    for line in text.splitlines():
        if line.startswith("Router>"):
            slot = None
        if m := HAL_SLOT.match(line):
            slot = m.group(1)
        elif slot and (m := HAL_RADIO.match(line)):
            key = "tx_power" if m.group(1) == "TxPower" else "utilization"
            out.setdefault(SLOT_BAND.get(slot, f"radio{slot}"), {})[key] = int(m.group(2))
    return out


HAL_CHANNEL = re.compile(r"^\s*(?:operating\s+|current\s+)?channel\s*(?:number)?\s*[:=]\s*(\d+)\b", re.I)


def parse_channels(text: str) -> dict[str, int]:
    """Canale per banda da `show wireless-hal current` (formato da confermare: righe "Slot: N" e "Channel: C")."""
    out: dict[str, int] = {}
    slot: str | None = None
    active = False
    for line in text.splitlines():
        if line.startswith("Router>"):
            active = "wireless-hal current" in line
            slot = None
            continue
        if not active:
            continue
        if m := HAL_SLOT.match(line):
            slot = m.group(1)
        elif slot and (m := HAL_CHANNEL.match(line)):
            out.setdefault(SLOT_BAND.get(slot, f"radio{slot}"), int(m.group(1)))
    return out


CPU_NOW = re.compile(r"^\s*CPU utilization:\s*(\d+)\s*%", re.I | re.M)
MEM_USE = re.compile(r"^\s*memory usage:\s*(\d+)\s*%", re.I | re.M)


def parse_cpu_mem(text: str) -> tuple[int | None, int | None]:
    """`show cpu status` ("CPU utilization: 4 %", prima riga = valore attuale) e `show mem status`."""
    cpu, mem = CPU_NOW.search(text), MEM_USE.search(text)
    return (int(cpu.group(1)) if cpu else None, int(mem.group(1)) if mem else None)


def parse_hal_statistic(text: str) -> dict[str, tuple[int, int]]:
    """`show wireless-hal statistic` (NWA50AX PRO, firmware 7.12): contatori per radio.
    Slot N diventa "wlan-N-1", come le interfacce SSID lette via SNMP; (ricevuti, trasmessi) dalla radio."""
    out: dict[str, tuple[int, int]] = {}
    slot: str | None = None
    rx = tx = None
    for line in text.splitlines():
        if line.rstrip().endswith(">") or line.startswith("Router>"):
            slot = None
        if m := HAL_SLOT.match(line):
            slot, rx, tx = m.group(1), None, None
            continue
        if slot and (m := HAL_BYTES.match(line)):
            if m.group(1) == "Received":
                rx = int(m.group(2))
            else:
                tx = int(m.group(2))
            if rx is not None and tx is not None:
                out[f"wlan-{slot}-1"] = (rx, tx)
    return out


def parse_port_status(text: str) -> dict[str, tuple[int, int]]:
    """`show port status`: le ultime due colonne sono TxBytes e RxBytes della porta cablata (uplink)."""
    header = None
    for line in text.splitlines():
        cols = line.split()
        if "TxBytes" in cols and "RxBytes" in cols:
            header = cols
        elif header and cols and cols[0] == "1" and len(cols) >= 3:
            try:
                tx, rx = int(cols[-2]), int(cols[-1])
            except ValueError:
                return {}
            return {"eth0": (rx, tx)}
    return {}


def parse_version(text: str) -> tuple[str | None, str | None, int | None]:
    """Estrae modello, firmware e uptime da `show version` (formato variabile: parsing tollerante)."""
    model = fw = None
    uptime = None
    for line in text.splitlines():
        low = line.lower()
        value = line.split(":", 1)[1].strip() if ":" in line else ""
        if not model and ("model name" in low or low.strip().startswith("model")):
            model = value or None
        elif not fw and "firmware version" in low:
            fw = value or None
        elif uptime is None and "uptime" in low:
            # "05:12:34", "3 days, 05:12:34", "1 day(s), 05:12:34"
            m = re.search(r"(?:(\d+)\s*day[^\d]*)?(\d+):(\d+):(\d+)", value)
            if m:
                d, h, mi, s = (int(x or 0) for x in m.groups())
                uptime = d * 86400 + h * 3600 + mi * 60 + s
    return model, fw, uptime


# host -> (password rifiutata, quando): la stessa password non viene ritentata prima di
# RETRY_AFTER secondi, altrimenti l'AP blocca l'IP del server come tentativo di forza bruta.
# Il nuovo tentativo serve perché un AP ancora "in blocco" rifiuta anche la password giusta.
RETRY_AFTER = 600
REJECTED_MSG = "Password SSH rifiutata: correggila in Impostazioni (nuovo tentativo tra 10 minuti)"
_rejected: dict[str, tuple[str, float]] = {}


async def collect(host: str, user: str, password: str, port: int = 22) -> ApReading:
    if not password:
        return ApReading(online=False, error="Password SSH non impostata: aggiungila in Impostazioni")
    rej = _rejected.get(host)
    if rej and rej[0] == password and time.monotonic() - rej[1] < RETRY_AFTER:
        return ApReading(online=False, error=REJECTED_MSG)
    try:
        text = await _shell(host, user, password, port)
    except asyncssh.PermissionDenied:
        _rejected[host] = (password, time.monotonic())
        return ApReading(online=False, error=REJECTED_MSG)
    except (OSError, asyncssh.Error, TimeoutError) as exc:
        return ApReading(online=False, error=f"SSH: {exc}")
    _rejected.pop(host, None)
    last_output[host] = (time.time(), text)

    model, fw, uptime = parse_version(text)
    clients = parse_stations(text)
    hal = parse_hal_radios(text)
    # bande: quelle dichiarate dalle radio (anche senza client), più quelle viste nei client
    radios: dict[str, int] = dict.fromkeys(hal, 0)
    for c in clients:
        radios[c.band or "?"] = radios.get(c.band or "?", 0) + 1
    channels = parse_channels(text)
    cpu, mem = parse_cpu_mem(text)
    return ApReading(
        online=True, model=model, firmware=fw, uptime_s=uptime, clients=clients, cpu_pct=cpu, mem_pct=mem,
        traffic={**parse_traffic(text), **parse_port_status(text), **parse_hal_statistic(text)},
        radios=[Radio(band=b, channel=channels.get(b), clients=n, **hal.get(b, {})) for b, n in sorted(radios.items())],
    )


# banda → slot della CLI ("wlan slotN"), come in "show wireless-hal statistic"
BAND_SLOT = {"2.4GHz": 1, "5GHz": 2, "6GHz": 3}


def power_commands(band: str, dbm: int) -> list[str]:
    """Potenza di una radio: "wlan slotN / output-power XXdBm". Non si usa "write": con Nebula attivo
    la configurazione permanente la gestisce il cloud, e il sistema la riapplica se viene sovrascritta."""
    return [f"wlan slot{BAND_SLOT[band]}", f"output-power {dbm}dBm", "exit"]


async def _session(host: str, user: str, password: str, port: int, lines: list[str], timeout: float = 40) -> str:
    async with asyncssh.connect(host, port=port, username=user, password=password, known_hosts=None,
                                connect_timeout=10) as conn:
        proc = await conn.create_process(term_type="vt100", term_size=(200, 5000))
        proc.stdin.write("\n".join([*lines, "exit"]) + "\n")
        chunks: list[str] = []

        async def reader():
            while data := await proc.stdout.read(65536):
                chunks.append(data)

        try:
            await asyncio.wait_for(reader(), timeout)
        except TimeoutError:
            pass
        proc.close()
        return "".join(chunks).replace("\r", "")


async def configure(host: str, user: str, password: str, port: int, commands: list[str]) -> str:
    """Esegue comandi in "configure terminal" e restituisce l'output (gli errori della CLI restano nel testo)."""
    return await _session(host, user, password, port, ["configure terminal", *commands, "exit"])


async def running_config(host: str, user: str, password: str, port: int = 22) -> str:
    text = await _session(host, user, password, port, ["show running-config"])
    start = text.find("Router> show running-config")
    return text[start:] if start >= 0 else text


CLI_ERROR = re.compile(r"(Parse error|command not found|ERROR:|Invalid)", re.I)


async def reboot(host: str, user: str, password: str, port: int = 22) -> None:
    """Riavvia l'AP con il comando "reboot" della CLI: la connessione cade, quindi non si attende risposta."""
    async with asyncssh.connect(host, port=port, username=user, password=password, known_hosts=None,
                                connect_timeout=10) as conn:
        proc = await conn.create_process(term_type="vt100")
        proc.stdin.write("reboot\n")
        try:
            await asyncio.wait_for(proc.stdout.read(4096), 5)
        except (TimeoutError, asyncssh.Error, OSError):
            pass
