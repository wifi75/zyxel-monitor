"""Configurazione letta da variabili d'ambiente / file .env."""
from dataclasses import dataclass
from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
