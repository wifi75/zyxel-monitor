"""Configurazione letta da variabili d'ambiente / file .env, con le modifiche fatte dal pannello."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class AccessPoint:
    name: str
    host: str
    method: str  # "snmp" | "ssh"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # Elenco AP: "NOME|IP|metodo" separati da virgola
    aps: str = (
        "ZONA NOTTE|192.168.1.11|ssh,SOGGIORNO|192.168.1.12|ssh,"
        "GARAGE|192.168.1.13|snmp,GIARDINO|192.168.1.14|snmp"
    )
    snmp_community: str = "public"
    ssh_user: str = "admin"
    ssh_password: str = ""

    # OPNsense (facoltativo): nomi dai lease DHCP e siti visitati dal DNS
    opnsense_url: str = ""
    opnsense_key: str = ""
    opnsense_secret: str = ""
    opnsense_verify_tls: bool = True
    opnsense_wan_if: str = "wan"   # interfaccia verso Internet (es. "opt1" per una VLAN del provider)
    # domini da non contare tra i "siti visitati" (rete locale, reverse DNS)
    local_domain: str = ""

    poll_interval: int = 60         # secondi tra una lettura e l'altra
    retention_days: int = 30         # giorni di storico conservati
    db_path: str = "data/monitor.db"

    secret_key: str = "cambia-questa-chiave"   # firma dei token di sessione
    session_hours: int = 12

    def access_points(self) -> list[AccessPoint]:
        out = []
        for item in self.aps.split(","):
            parts = [p.strip() for p in item.split("|")]
            if len(parts) == 3 and parts[2] in ("snmp", "ssh"):
                out.append(AccessPoint(*parts))
        return out


# impostazioni modificabili dal pannello: il valore salvato nel DB vale più del .env
EDITABLE = (
    "opnsense_url", "opnsense_key", "opnsense_secret", "opnsense_verify_tls", "opnsense_wan_if",
    "local_domain", "poll_interval", "retention_days",
)


def _db_overrides(db_path: str) -> dict[str, str]:
    path = Path(db_path)
    if not path.exists():
        return {}
    try:
        with closing(sqlite3.connect(path, timeout=10)) as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
    except sqlite3.Error:        # tabella non ancora creata
        return {}
    return {k: v for k, v in rows if k in EDITABLE}


@lru_cache
def get_settings() -> Settings:
    base = Settings()
    overrides = _db_overrides(base.db_path)
    return Settings(**overrides) if overrides else base
