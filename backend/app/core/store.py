"""Access point e impostazioni gestiti dal pannello (tabelle access_points e settings)."""
from dataclasses import dataclass, fields

from .config import get_settings
from .db import connect


@dataclass
class ApConfig:
    name: str
    host: str
    method: str                  # "snmp" | "ssh"
    enabled: bool = True
    snmp_version: str = "2c"     # "1" | "2c" | "3"
    snmp_community: str = ""
    snmp_user: str = ""
    snmp_auth_proto: str = "SHA"
    snmp_auth_pass: str = ""
    snmp_priv_proto: str = "AES"
    snmp_priv_pass: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_password: str = ""
    id: int | None = None


# mai restituiti dall'API: il pannello sa solo se sono impostati
SECRETS = ("snmp_community", "snmp_auth_pass", "snmp_priv_pass", "ssh_password")
CREDENTIALS = {
    "snmp": ("snmp_version", "snmp_community", "snmp_user", "snmp_auth_proto", "snmp_auth_pass",
             "snmp_priv_proto", "snmp_priv_pass"),
    "ssh": ("ssh_port", "ssh_user", "ssh_password"),
}
_COLS = [f.name for f in fields(ApConfig) if f.name != "id"]


def _from_row(row) -> ApConfig:
    d = dict(row)
    d["enabled"] = bool(d["enabled"])
    return ApConfig(**d)


def list_aps(enabled_only: bool = False) -> list[ApConfig]:
    sql = "SELECT * FROM access_points" + (" WHERE enabled = 1" if enabled_only else "")
    with connect() as db:
        return [_from_row(r) for r in db.execute(sql + " ORDER BY name COLLATE NOCASE")]


def get_ap(ap_id: int) -> ApConfig | None:
    with connect() as db:
        row = db.execute("SELECT * FROM access_points WHERE id = ?", (ap_id,)).fetchone()
    return _from_row(row) if row else None


def conflict(ap: ApConfig) -> str | None:
    """Messaggio d'errore se un altro AP ha lo stesso nome o lo stesso indirizzo."""
    with connect() as db:
        row = db.execute(
            "SELECT name, host FROM access_points WHERE id IS NOT ? AND (lower(name) = lower(?) OR host = ?)",
            (ap.id, ap.name, ap.host),
        ).fetchone()
    if not row:
        return None
    if row["name"].lower() == ap.name.lower():
        return f"Esiste già un access point chiamato {row['name']}"
    return f"L'indirizzo {ap.host} è già usato da {row['name']}"


def _insert(db, ap: ApConfig) -> int:
    cur = db.execute(
        f"INSERT INTO access_points({', '.join(_COLS)}) VALUES ({', '.join('?' * len(_COLS))})",
        [getattr(ap, c) for c in _COLS],
    )
    return cur.lastrowid


def save_ap(ap: ApConfig) -> int:
    with connect() as db:
        if ap.id is None:
            return _insert(db, ap)
        db.execute(
            f"UPDATE access_points SET {', '.join(f'{c} = ?' for c in _COLS)} WHERE id = ?",
            [*(getattr(ap, c) for c in _COLS), ap.id],
        )
        return ap.id


def rename_history(old: str, new: str) -> None:
    """Il nome è la chiave dello storico: rinominando un AP si portano dietro grafici ed eventi."""
    with connect() as db:
        for table in ("ap_status", "clients", "events", "samples"):
            db.execute(f"UPDATE {table} SET ap = ? WHERE ap = ?", (new, old))


def delete_ap(ap: ApConfig) -> None:
    with connect() as db:
        db.execute("DELETE FROM access_points WHERE id = ?", (ap.id,))
        db.execute("DELETE FROM ap_status WHERE ap = ?", (ap.name,))
        db.execute("DELETE FROM clients WHERE ap = ?", (ap.name,))


def copy_credentials(ap: ApConfig) -> int:
    """Copia le credenziali di `ap` su tutti gli altri AP con lo stesso protocollo."""
    cols = CREDENTIALS[ap.method]
    with connect() as db:
        cur = db.execute(
            f"UPDATE access_points SET {', '.join(f'{c} = ?' for c in cols)} WHERE method = ? AND id <> ?",
            [*(getattr(ap, c) for c in cols), ap.method, ap.id],
        )
        return cur.rowcount


def set_settings(values: dict) -> None:
    rows = [(k, ("true" if v else "false") if isinstance(v, bool) else str(v)) for k, v in values.items()]
    with connect() as db:
        db.executemany(
            "INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            rows,
        )
    get_settings.cache_clear()


def seed_from_env() -> None:
    """Al primo avvio importa gli AP e le credenziali del .env; poi comanda il pannello."""
    with connect() as db:
        if db.execute("SELECT 1 FROM settings WHERE key = '_seeded'").fetchone():
            return
        if not db.execute("SELECT 1 FROM access_points").fetchone():
            s = get_settings()
            for ap in s.access_points():
                _insert(db, ApConfig(
                    name=ap.name, host=ap.host, method=ap.method, snmp_community=s.snmp_community,
                    ssh_user=s.ssh_user, ssh_password=s.ssh_password,
                ))
        db.execute("INSERT INTO settings(key, value) VALUES ('_seeded', '1')")
