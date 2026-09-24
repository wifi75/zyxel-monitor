"""Lettura AP via SNMP v2c (net-snmp CLI) — MIB Zyxel 1.3.6.1.4.1.890.1.15.3.

OID verificati su WAC6103D-I e NWA1123-AC PRO (firmware 6.28):
  .3.1.11.0 modello, .3.1.6.0 firmware
  .3.5.1.1.{1 canale, 2 n.client, 5 indice radio}.<radio>
  .3.5.2.1.{2 MAC, 3 ora connessione, 4 SSID, 5 RSSI}.<radio>.<n>
"""
import asyncio
import datetime as dt
import re

from .base import ApReading, Client, Radio, band_for_radio

ZY = ".1.3.6.1.4.1.890.1.15.3"
SYS_UPTIME = ".1.3.6.1.2.1.1.3.0"       # uptime dell'agente SNMP (riparte a ogni config)
HOST_UPTIME = ".1.3.6.1.2.1.25.1.1.0"   # uptime reale del sistema
IF_NAME = ".1.3.6.1.2.1.31.1.1.1.1"
IF_IN = ".1.3.6.1.2.1.31.1.1.1.6"
IF_OUT = ".1.3.6.1.2.1.31.1.1.1.10"
# interfacce di cui conserviamo il traffico: uplink cablato e SSID per radio
IFACE_RE = re.compile(r"^(eth0|wlan-\d+-\d+)$")


async def _run(args: list[str], timeout: float = 25) -> dict[str, str]:
    """Esegue snmpget/snmpbulkwalk e restituisce {oid: valore}. Stringhe in hex (-Ox)."""
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        raise RuntimeError("timeout SNMP") from None
    if proc.returncode != 0:
        # net-snmp al primo avvio scrive "Created directory: ..." prima del vero errore
        lines = [x for x in err.decode().splitlines() if x.strip() and not x.startswith("Created directory")]
        raise RuntimeError(" ".join(lines) or "errore SNMP")
    result = {}
    for line in out.decode(errors="replace").splitlines():
        oid, _, value = line.partition(" ")
        if oid.startswith("."):
            result[oid] = value.strip().strip('"').strip()
    return result


def _hex_bytes(value: str) -> bytes:
    try:
        return bytes.fromhex(value.replace(" ", ""))
    except ValueError:
        return value.encode()


def _text(value: str) -> str:
    return _hex_bytes(value).decode(errors="replace").strip()


def _datetime(value: str) -> int | None:
    b = _hex_bytes(value)
    if len(b) < 7:
        return None
    try:
        local = dt.datetime(int.from_bytes(b[0:2], "big"), b[2], b[3], b[4], b[5], b[6])
        return int(local.timestamp())
    except ValueError:
        return None


def auth_args(ap) -> list[str]:
    """Parametri di autenticazione net-snmp per v1, v2c o v3 (utente, autenticazione, cifratura)."""
    if ap.snmp_version != "3":
        return ["-v", ap.snmp_version, "-c", ap.snmp_community or "public"]
    args = ["-v3", "-u", ap.snmp_user]
    if not ap.snmp_auth_pass:
        return [*args, "-l", "noAuthNoPriv"]
    args += ["-a", ap.snmp_auth_proto, "-A", ap.snmp_auth_pass]
    if not ap.snmp_priv_pass:
        return [*args, "-l", "authNoPriv"]
    return [*args, "-l", "authPriv", "-x", ap.snmp_priv_proto, "-X", ap.snmp_priv_pass]


async def collect(host: str, auth: list[str]) -> ApReading:
    base = [*auth, "-On", "-Oq", "-Ox", "-Ot", "-t", "3", "-r", "2", host]
    walk = "snmpwalk" if auth[:2] == ["-v", "1"] else "snmpbulkwalk"   # GETBULK non esiste in v1
    try:
        info, zy, names, ins, outs = await asyncio.gather(
            _run(["snmpget", *base, HOST_UPTIME, SYS_UPTIME, f"{ZY}.1.11.0", f"{ZY}.1.6.0"]),
            _run([walk, *base, f"{ZY}.5"]),
            _run([walk, *base, IF_NAME]),
            _run([walk, *base, IF_IN]),
            _run([walk, *base, IF_OUT]),
        )
    except FileNotFoundError:
        return ApReading(online=False, error="Comandi SNMP non installati sul server (pacchetto snmp)")
    except (RuntimeError, OSError) as exc:
        return ApReading(online=False, error=str(exc))

    reading = ApReading(
        online=True,
        uptime_s=int(info.get(HOST_UPTIME) or info.get(SYS_UPTIME) or 0) // 100,
        model=_text(info.get(f"{ZY}.1.11.0", "")) or None,
        firmware=_text(info.get(f"{ZY}.1.6.0", "")) or None,
    )

    # radio
    radio_cols: dict[str, dict[int, str]] = {}
    client_cols: dict[str, dict[int, str]] = {}
    for oid, value in zy.items():
        if oid.startswith(f"{ZY}.5.1.1."):
            col, radio = oid[len(f"{ZY}.5.1.1."):].split(".", 1)
            radio_cols.setdefault(radio, {})[int(col)] = value
        elif oid.startswith(f"{ZY}.5.2.1."):
            col, idx = oid[len(f"{ZY}.5.2.1."):].split(".", 1)
            client_cols.setdefault(idx, {})[int(col)] = value

    for radio, cols in sorted(radio_cols.items()):
        reading.radios.append(Radio(
            band=band_for_radio(int(radio)),
            channel=int(cols[1]) if cols.get(1, "").isdigit() else None,
            clients=int(cols.get(2, "0") or 0),
        ))

    for idx, cols in client_cols.items():
        mac_raw = _hex_bytes(cols.get(2, ""))
        if len(mac_raw) != 6:
            continue
        rssi = _text(cols.get(5, ""))
        reading.clients.append(Client(
            mac=":".join(f"{b:02x}" for b in mac_raw),
            band=band_for_radio(int(idx.split(".")[0])),
            ssid=_text(cols.get(4, "")) or None,
            rssi_dbm=int(rssi) if re.fullmatch(r"-?\d+", rssi) else None,
            connected_at=_datetime(cols.get(3, "")),
        ))

    # traffico per interfaccia
    for oid, value in names.items():
        name = _text(value)
        if not IFACE_RE.match(name):
            continue
        ifidx = oid.rsplit(".", 1)[1]
        rx, tx = ins.get(f"{IF_IN}.{ifidx}"), outs.get(f"{IF_OUT}.{ifidx}")
        if rx and tx and rx.isdigit() and tx.isdigit():
            reading.traffic[name] = (int(rx), int(tx))

    return reading
