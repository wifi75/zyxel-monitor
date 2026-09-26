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

-- access point gestiti dal pannello (al primo avvio importati dal .env)
CREATE TABLE IF NOT EXISTS access_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    host            TEXT NOT NULL,
    method          TEXT NOT NULL,              -- snmp | ssh
    enabled         INTEGER NOT NULL DEFAULT 1,
    snmp_version    TEXT NOT NULL DEFAULT '2c', -- 1 | 2c | 3
    snmp_community  TEXT NOT NULL DEFAULT '',
    snmp_user       TEXT NOT NULL DEFAULT '',
    snmp_auth_proto TEXT NOT NULL DEFAULT 'SHA',
    snmp_auth_pass  TEXT NOT NULL DEFAULT '',
    snmp_priv_proto TEXT NOT NULL DEFAULT 'AES',
    snmp_priv_pass  TEXT NOT NULL DEFAULT '',
    ssh_port        INTEGER NOT NULL DEFAULT 22,
    ssh_user        TEXT NOT NULL DEFAULT '',
    ssh_password    TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_access_points_name ON access_points(name);

-- ogni dispositivo mai visto: primo e ultimo avvistamento, riconosciuto o no
CREATE TABLE IF NOT EXISTS devices (
    mac        TEXT PRIMARY KEY,
    first_seen INTEGER NOT NULL,
    last_seen  INTEGER NOT NULL,
    last_ap    TEXT,
    last_ip    TEXT,
    hostname   TEXT,
    known      INTEGER NOT NULL DEFAULT 0
);

-- segnale di ogni client a ogni lettura
CREATE TABLE IF NOT EXISTS rssi_samples (
    ts   INTEGER NOT NULL,
    mac  TEXT NOT NULL,
    ap   TEXT NOT NULL,
    rssi INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_rssi_mac ON rssi_samples(mac, ts);
CREATE INDEX IF NOT EXISTS ix_rssi_ts ON rssi_samples(ts);

-- stato della linea Internet (gateway di OPNsense) a ogni lettura
CREATE TABLE IF NOT EXISTS line_samples (
    ts       INTEGER NOT NULL,
    gateway  TEXT NOT NULL,
    online   INTEGER NOT NULL,
    delay_ms REAL,
    loss_pct REAL
);
CREATE INDEX IF NOT EXISTS ix_line_ts ON line_samples(gateway, ts);

-- configurazione centralizzata delle radio: scope 'site' (vale per tutti) o 'ap:<id>' (personalizzazione)
CREATE TABLE IF NOT EXISTS radio_policy (
    scope    TEXT NOT NULL,
    band     TEXT NOT NULL,              -- 2.4GHz | 5GHz
    tx_power INTEGER,                    -- dBm; NULL = non gestito
    PRIMARY KEY (scope, band)
);

-- copie della running-config degli AP (rete di sicurezza prima di modifiche o del distacco da Nebula)
CREATE TABLE IF NOT EXISTS config_backups (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ap   TEXT NOT NULL,
    ts   INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_backups_ap ON config_backups(ap, ts);

-- impostazioni del sito applicate a tutti gli AP (rete, radio, sistema): valore in JSON
CREATE TABLE IF NOT EXISTS site_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- impostazioni salvate dal pannello: hanno la precedenza sul .env
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
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


# colonne aggiunte dopo la prima versione: ADD COLUMN è sicuro su SQLite (non ricrea la tabella)
LATER_COLUMNS = {
    "ap_status": {"cpu_pct": "INTEGER", "mem_pct": "INTEGER"},
    "radio_policy": {"channel": "TEXT", "width": "TEXT"},
    "devices": {"critical": "INTEGER NOT NULL DEFAULT 0"},     # dispositivo importante: avviso se si scollega
    "users": {"role": "TEXT NOT NULL DEFAULT 'admin'"},         # admin | viewer (sola lettura)
}


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, cols in LATER_COLUMNS.items():
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for name, kind in cols.items():
                if name not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
