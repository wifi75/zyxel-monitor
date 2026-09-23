"""Accesso SQLite: schema e connessione."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import get_settings

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    is_default    INTEGER NOT NULL DEFAULT 1
);

-- stato attuale di ogni AP (una riga per AP)
CREATE TABLE IF NOT EXISTS ap_status (
    ap        TEXT PRIMARY KEY,
    host      TEXT NOT NULL,
    method    TEXT NOT NULL,
    online    INTEGER NOT NULL,
    model     TEXT,
    firmware  TEXT,
    uptime_s  INTEGER,
    clients   INTEGER,
    radios    TEXT,           -- JSON: [{"band","channel","clients"}]
    error     TEXT,
    last_seen INTEGER,
    updated   INTEGER NOT NULL
);

-- client connessi adesso (riscritta a ogni ciclo)
CREATE TABLE IF NOT EXISTS clients (
    mac          TEXT PRIMARY KEY,
    ap           TEXT NOT NULL,
    ip           TEXT,
    hostname     TEXT,
    ssid         TEXT,
    band         TEXT,
    rssi_dbm     INTEGER,
    tx_rate      INTEGER,
    rx_rate      INTEGER,
    capability   TEXT,
    connected_at INTEGER,
    updated      INTEGER NOT NULL
);

-- storico connessioni / disconnessioni / roaming
CREATE TABLE IF NOT EXISTS events (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    INTEGER NOT NULL,
    kind  TEXT NOT NULL,      -- connect | disconnect | roam | ap_down | ap_up
    mac   TEXT,
    name  TEXT,
    ap    TEXT,
    info  TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts);

-- campioni: contatori di traffico grezzi e numero client
CREATE TABLE IF NOT EXISTS samples (
    ts        INTEGER NOT NULL,
    ap        TEXT NOT NULL,
    iface     TEXT NOT NULL,  -- nome interfaccia, "_clients" per il conteggio
    in_bytes  INTEGER,
    out_bytes INTEGER
);
CREATE INDEX IF NOT EXISTS ix_samples ON samples(ap, iface, ts);

-- query DNS lette da OPNsense (sito già ridotto al dominio principale)
CREATE TABLE IF NOT EXISTS dns (
    ts        INTEGER NOT NULL,
    client_ip TEXT NOT NULL,
    site      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dns_ts ON dns(ts);

-- nomi assegnati a mano ai dispositivi
CREATE TABLE IF NOT EXISTS aliases (
    mac  TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
"""


def _path() -> Path:
    p = Path(get_settings().db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect():
    conn = sqlite3.connect(_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
