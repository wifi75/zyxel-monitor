"""Strutture dati comuni ai collector."""
from dataclasses import dataclass, field


@dataclass
class Client:
    mac: str
    band: str | None = None
    ssid: str | None = None
    ip: str | None = None
    rssi_dbm: int | None = None
    tx_rate: int | None = None       # Mbps
    rx_rate: int | None = None       # Mbps
    capability: str | None = None
    connected_at: int | None = None  # epoch


@dataclass
class Radio:
    band: str
    channel: int | None
    clients: int


@dataclass
class ApReading:
    online: bool
    model: str | None = None
    firmware: str | None = None
    uptime_s: int | None = None
    radios: list[Radio] = field(default_factory=list)
    clients: list[Client] = field(default_factory=list)
    # nome interfaccia -> (byte ricevuti, byte trasmessi), contatori cumulativi
    traffic: dict[str, tuple[int, int]] = field(default_factory=dict)
    error: str | None = None


def band_for_radio(idx: int) -> str:
    return {1: "2.4GHz", 2: "5GHz", 3: "6GHz"}.get(idx, f"radio{idx}")
