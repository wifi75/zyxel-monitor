"""Esportazione in CSV (separatore ";" per Excel in italiano) di dispositivi ed eventi."""
import csv
import datetime as dt
import io
import time

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from .core.db import connect
from .core.security import current_user
from .oui import vendor

router = APIRouter(prefix="/api/export", dependencies=[Depends(current_user)])

BOM = "﻿"      # Excel riconosce l'UTF-8 e mostra bene le lettere accentate


def _csv(name: str, header: list[str], rows: list[list]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    w.writerows(rows)
    return Response(BOM + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _when(ts: int | None) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""


def _yes(v) -> str:
    return "sì" if v else "no"


@router.get("/devices.csv")
def devices_csv():
    with connect() as db:
        rows = db.execute(
            """SELECT d.*, a.name AS alias FROM devices d LEFT JOIN aliases a ON a.mac = d.mac
               ORDER BY d.last_seen DESC""").fetchall()
    return _csv("dispositivi.csv",
                ["nome", "hostname", "mac", "produttore", "ip", "ultimo AP", "prima volta", "ultima volta",
                 "riconosciuto", "importante"],
                [[r["alias"] or "", r["hostname"] or "", r["mac"], vendor(r["mac"]) or "", r["last_ip"] or "",
                  r["last_ap"] or "", _when(r["first_seen"]), _when(r["last_seen"]), _yes(r["known"]),
                  _yes(r["critical"])] for r in rows])


@router.get("/events.csv")
def events_csv(days: float = 7):
    since = int(time.time() - max(1.0, min(days, 90.0)) * 86400)
    with connect() as db:
        rows = db.execute("SELECT * FROM events WHERE ts >= ? ORDER BY ts DESC", (since,)).fetchall()
    return _csv("eventi.csv", ["quando", "evento", "dispositivo", "mac", "AP", "dettagli"],
                [[_when(r["ts"]), r["kind"], r["name"] or "", r["mac"] or "", r["ap"] or "", r["info"] or ""]
                 for r in rows])
