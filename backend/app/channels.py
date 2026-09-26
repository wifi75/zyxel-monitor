"""Piano dei canali: sovrapposizioni fra AP e proposta di canali, solo come consiglio.

Il pannello oggi monitora e basta (la configurazione la fa Nebula): qui non si invia nulla agli AP,
la proposta va applicata da Nebula o dalla pagina Configurazione quando la gestione sarà accesa.
"""
import json

from fastapi import APIRouter, Depends

from .core.db import connect
from .core.security import current_user

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

BUSY_PCT = 60          # occupazione del canale oltre la quale la radio fatica
# 2.4 GHz: gli unici tre canali che non si sovrappongono
CLEAN_24 = (1, 6, 11)
# 5 GHz: un canale per blocco da 80 MHz (UNII-1, UNII-2, UNII-2e ×2); 149+ in Italia ha potenza ridotta
CLEAN_5 = (36, 52, 100, 116)


def _overlap_24(a: int, b: int) -> bool:
    return a != b and abs(a - b) < 5


def _block_5(ch: int) -> int:
    """Blocco da 80 MHz a cui appartiene un canale (36-48 → 36, 52-64 → 52, …)."""
    return 36 + (ch - 36) // 16 * 16 if ch >= 36 else ch


def _suggest(radios: list[dict], clean: tuple[int, ...]) -> dict[str, int]:
    """Canali puliti assegnati partendo dall'AP più carico; chi è già su un canale pulito libero lo tiene."""
    order = sorted(radios, key=lambda r: -(r["clients"] or 0))
    taken: dict[int, int] = {c: 0 for c in clean}
    out: dict[str, int] = {}
    for r in order:
        ch = r["channel"]
        if ch in taken and taken[ch] == 0:
            out[r["ap"]] = ch
            taken[ch] += 1
    for r in order:
        if r["ap"] in out:
            continue
        best = min(clean, key=lambda c: taken[c])
        out[r["ap"]] = best
        taken[best] += 1
    return out


def analyse(aps: list[dict]) -> dict:
    bands: dict[str, dict] = {}
    for band, clean in (("2.4GHz", CLEAN_24), ("5GHz", CLEAN_5)):
        radios = [
            {"ap": a["ap"], "channel": r.get("channel"), "auto": r.get("channel_auto"),
             "utilization": r.get("utilization"), "clients": r.get("clients") or 0, "tx_power": r.get("tx_power")}
            for a in aps if a.get("online") for r in a.get("radios", []) if r.get("band") == band
        ]
        known = [r for r in radios if r["channel"]]
        issues = []
        # stesso canale: un avviso per canale con tutti gli AP coinvolti, non uno per ogni coppia
        by_channel: dict[int, list[str]] = {}
        for r in known:
            by_channel.setdefault(r["channel"], []).append(r["ap"])
        for ch, names in by_channel.items():
            if len(names) > 1:
                issues.append({"kind": "same", "aps": names, "channel": ch})
        for i, a in enumerate(known):
            for b in known[i + 1:]:
                if a["channel"] == b["channel"]:
                    continue
                elif band == "2.4GHz" and _overlap_24(a["channel"], b["channel"]):
                    issues.append({"kind": "overlap", "aps": [a["ap"], b["ap"]], "channel": a["channel"]})
                elif band == "5GHz" and _block_5(a["channel"]) == _block_5(b["channel"]):
                    issues.append({"kind": "overlap", "aps": [a["ap"], b["ap"]], "channel": a["channel"]})
        for r in radios:
            if r["utilization"] is not None and r["utilization"] >= BUSY_PCT:
                issues.append({"kind": "busy", "aps": [r["ap"]], "channel": r["channel"], "pct": r["utilization"]})
            if band == "2.4GHz" and r["channel"] and r["channel"] not in CLEAN_24:
                issues.append({"kind": "unclean", "aps": [r["ap"]], "channel": r["channel"]})
        conflict = any(i["kind"] in ("same", "overlap", "unclean") for i in issues)
        suggested = _suggest(known, clean) if conflict else {r["ap"]: r["channel"] for r in known}
        bands[band] = {"radios": radios, "issues": issues, "suggested": suggested,
                       "changes": {ap: ch for ap, ch in suggested.items()
                                   if ch != next(r["channel"] for r in known if r["ap"] == ap)}}
    return {"busy_pct": BUSY_PCT, "bands": bands}


@router.get("/channels")
def channels():
    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT ap, online, radios FROM ap_status ORDER BY ap")]
    for r in rows:
        r["radios"] = json.loads(r["radios"] or "[]")
        r["online"] = bool(r["online"])
    return analyse(rows)
