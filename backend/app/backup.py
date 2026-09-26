"""Copia del database: scaricabile dal pannello e salvata ogni notte.

La copia notturna va in BACKUP_DIR (predefinita: cartella "backups" accanto al DB). Montando lì una cartella
del NAS in Portainer, lo storico sopravvive anche alla perdita del volume Docker.
"""
import datetime as dt
import logging
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .core.config import get_settings
from .core.security import current_user

log = logging.getLogger("backup")
router = APIRouter(prefix="/api/backup", dependencies=[Depends(current_user)])

KEEP = 7            # copie notturne conservate
NIGHT_HOUR = 3


def backup_dir() -> Path:
    return Path(os.environ.get("BACKUP_DIR") or Path(get_settings().db_path).parent / "backups")


def copy_to(dest: Path) -> Path:
    """Copia coerente anche col poller che scrive (API di backup di SQLite, non una copia del file)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(get_settings().db_path)) as src, closing(sqlite3.connect(dest)) as out:
        src.backup(out)
    return dest


def nightly() -> Path | None:
    """Chiamato dal poller: una copia al giorno dopo le 3, le più vecchie oltre KEEP si cancellano."""
    now = dt.datetime.now()
    folder = backup_dir()
    dest = folder / f"monitor-{now:%Y%m%d}.db"
    if now.hour < NIGHT_HOUR or dest.exists():
        return None
    try:
        copy_to(dest)
    except (OSError, sqlite3.Error) as exc:
        log.warning("backup notturno non riuscito: %s", exc)
        return None
    for old in sorted(folder.glob("monitor-*.db"))[:-KEEP]:
        old.unlink(missing_ok=True)
    log.info("backup notturno salvato in %s", dest)
    return dest


@router.get("")
def status():
    folder = backup_dir()
    files = sorted(folder.glob("monitor-*.db"), reverse=True) if folder.exists() else []
    return {"folder": str(folder), "keep": KEEP,
            "files": [{"name": f.name, "size": f.stat().st_size, "ts": int(f.stat().st_mtime)} for f in files]}


@router.get("/download")
def download():
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    copy_to(Path(tmp))
    name = f"zyxel-monitor-{dt.datetime.now():%Y%m%d-%H%M}.db"
    return FileResponse(tmp, filename=name, media_type="application/octet-stream",
                        background=BackgroundTask(os.unlink, tmp))
