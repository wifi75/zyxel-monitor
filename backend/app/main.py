"""Avvio FastAPI: API, collector in background e frontend statico."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .core.db import init_db
from .core.security import ensure_default_user
from .core.version import APP_AUTHOR, APP_NAME, APP_VERSION
from .poller import run_forever

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_default_user()
    task = asyncio.create_task(run_forever())
    yield
    task.cancel()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=f"Monitoraggio access point Zyxel — Ideato e sviluppato da {APP_AUTHOR}",
    lifespan=lifespan,
)
app.include_router(router)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = STATIC_DIR / path
        if path and file.is_file() and STATIC_DIR in file.resolve().parents:
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
