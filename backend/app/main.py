"""Avvio FastAPI: API, collector in background e frontend statico."""
import asyncio
import json
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .alerts import router as alerts_router
from .api import router
from .backup import router as backup_router
from .export_api import router as export_router
from .users_api import router as users_router
from .channels import router as channels_router
from .core.db import init_db
from .core.security import ensure_default_user, read_token, role_of
from .core.store import seed_from_env
from .core.version import APP_AUTHOR, APP_NAME, APP_VERSION
from .poller import run_forever
from .insights_api import router as insights_router
from .nebula_api import router as nebula_router
from .policy_api import router as policy_router
from .report import router as report_router
from .settings_api import router as settings_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_default_user()
    if os.environ.get("ZM_DEMO"):
        # modalità dimostrativa (screenshot): nessuna lettura degli AP, dati preparati da scripts/demo_data.py
        _load_demo()
        yield
        return
    seed_from_env()
    task = asyncio.create_task(run_forever())
    yield
    task.cancel()


def _load_demo() -> None:
    from .core.db import connect
    from .poller import internet_state
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = '_demo_internet'").fetchone()
    if row:
        internet_state.update(json.loads(row["value"]))


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=f"Monitoraggio access point Zyxel — Ideato e sviluppato da {APP_AUTHOR}",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(settings_router)
app.include_router(insights_router)
app.include_router(nebula_router)
app.include_router(policy_router)
app.include_router(alerts_router)
app.include_router(channels_router)
app.include_router(report_router)
app.include_router(backup_router)
app.include_router(export_router)
app.include_router(users_router)

# richieste che cambiano qualcosa ma restano permesse anche agli utenti in sola lettura
VIEWER_WRITES = ("/api/login", "/api/password", "/api/layout")


@app.middleware("http")
async def read_only_users(request: Request, call_next):
    """Gli utenti in sola lettura vedono tutto ma non possono modificare nulla (AP, impostazioni, dispositivi)."""
    path = request.url.path
    if request.method not in ("GET", "HEAD", "OPTIONS") and path.startswith("/api/") \
            and not path.startswith(VIEWER_WRITES):
        auth = request.headers.get("authorization", "")
        user = read_token(auth[7:]) if auth.lower().startswith("bearer ") else None
        if user and role_of(user) != "admin":
            return JSONResponse({"detail": "Utente in sola lettura: non puoi modificare"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Intestazioni di sicurezza su ogni risposta; HSTS solo quando si arriva in HTTPS (anche dietro proxy)."""
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.headers.get("x-forwarded-proto", request.url.scheme) == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return resp

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = STATIC_DIR / path
        if path and file.is_file() and STATIC_DIR in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
