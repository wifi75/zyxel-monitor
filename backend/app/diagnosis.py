"""Diagnosi di un dispositivo: quante volte si è scollegato, con che segnale e perché, in parole semplici.

Si parte dagli eventi già registrati (collegato, scollegato, roaming) e dai campioni di segnale; a ogni
scollegamento si guarda il segnale subito prima, l'AP, la banda e cosa è successo sull'AP in quel momento
(riconfigurazioni, AP spento). Le cause proposte sono ipotesi motivate, con il rimedio.
"""
import time
from statistics import median

from fastapi import APIRouter, Depends

from . import site_config
from .core.db import connect
from .core.security import current_user

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])

WEAK_DBM = -75          # sotto questo valore il segnale è debole anche senza espulsione
NEAR = 3                # dBm di margine attorno alla soglia di espulsione
CONFIG_WINDOW = 120     # un distacco entro 2 minuti da una riconfigurazione dell'AP le è attribuito
SHORT_S = 300           # connessioni più brevi di 5 minuti = instabili


def _kickout() -> int | None:
    v = site_config.load().get("rssi_kickout")
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v or None            # 0 = disattivata


def analyse(events: list[dict], signal_at, config_times: dict[str, list[int]], down_times: dict[str, list[int]],
            kickout: int | None, siblings: int, hours: float) -> dict:
    """Cuore della diagnosi, senza database: facile da provare."""
    drops = [e for e in events if e["kind"] == "disconnect"]
    roams = [e for e in events if e["kind"] == "roam"]
    connects = [e for e in events if e["kind"] == "connect"]
    detail = []
    for d in drops:
        rssi = signal_at(d["ts"])
        reconf = any(0 <= d["ts"] - t <= CONFIG_WINDOW for t in config_times.get(d["ap"], []))
        ap_down = any(abs(d["ts"] - t) <= CONFIG_WINDOW for t in down_times.get(d["ap"], []))
        weak = rssi is not None and ((kickout is not None and rssi <= kickout + NEAR) or rssi <= WEAK_DBM)
        cause = "ap" if ap_down else "config" if reconf else "weak" if weak else "other"
        detail.append({**d, "rssi": rssi, "cause": cause})

    # durata delle connessioni: da un "connesso" al "scollegato" successivo
    sessions, start = [], None
    for e in events:
        if e["kind"] == "connect":
            start = e["ts"]
        elif e["kind"] == "disconnect" and start is not None:
            sessions.append(e["ts"] - start)
            start = None
    rssis = [d["rssi"] for d in detail if d["rssi"] is not None]
    stats = {
        "hours": hours, "drops": len(drops), "roams": len(roams),
        "median_session_min": round(median(sessions) / 60, 1) if sessions else None,
        "short_sessions": sum(1 for s in sessions if s < SHORT_S),
        "rssi_at_drop": round(sum(rssis) / len(rssis)) if rssis else None,
        "kickout": kickout, "siblings": siblings,
    }

    findings = []
    n = len(drops)
    by = {c: sum(1 for d in detail if d["cause"] == c) for c in ("weak", "config", "ap", "other")}
    if n == 0:
        findings.append({"level": "ok", "title": "Collegamento stabile",
                         "text": f"Nessuno scollegamento nelle ultime {hours:g} ore."})
    else:
        lvl = "bad" if n >= 6 else "warn"
        extra = f", di cui {stats['short_sessions']} durati meno di 5 minuti" if stats["short_sessions"] else ""
        times = "volta" if n == 1 else "volte"
        findings.append({"level": lvl, "title": f"Si è scollegato {n} {times} in {hours:g} ore",
                         "text": f"Connessioni tipiche di {stats['median_session_min']} minuti{extra}."
                         if stats["median_session_min"] is not None else "Connessioni molto brevi."})
    if by["weak"] and by["weak"] >= max(2, n // 3):
        if kickout is not None:
            findings.append({"level": "bad", "title": "Staccato dall'AP per segnale debole",
                             "text": f"{by['weak']} distacchi su {n} con il segnale attorno alla soglia di espulsione "
                                     f"({kickout} dBm): segnale medio al distacco {stats['rssi_at_drop']} dBm. "
                                     "L'AP lo stacca, lui si ricollega, e così via.",
                             "fix": f"Abbassa «Espulsione dei segnali deboli» da {kickout} a -80 dBm o spegnila "
                                    "(Configurazione o Nebula → Smart steering), oppure avvicina il dispositivo "
                                    "all'AP."})
        else:
            findings.append({"level": "warn", "title": "Segnale debole al momento del distacco",
                             "text": f"{by['weak']} distacchi su {n} con segnale sotto {WEAK_DBM} dBm "
                                     f"(medio {stats['rssi_at_drop']} dBm).",
                             "fix": "Il dispositivo è al limite della copertura: avvicinalo all'AP o aggiungi "
                                    "copertura."})
    if by["config"]:
        findings.append({"level": "bad", "title": "Staccato da una riconfigurazione dell'AP",
                         "text": f"{by['config']} distacchi subito dopo una modifica della configurazione dell'AP "
                                 "(il Wi-Fi riparte per qualche secondo).",
                         "fix": "Controlla in Eventi le voci «Configurazione»: se si ripetono, spegni la gestione dal "
                                "pannello o togli la voce che viene rimandata."})
    if by["ap"]:
        findings.append({"level": "warn", "title": "L'AP si è spento o riavviato",
                         "text": f"{by['ap']} distacchi mentre l'AP risultava irraggiungibile.",
                         "fix": "Controlla alimentazione e cavo dell'AP."})
    bands = [c["info"] for c in connects if c.get("info") in ("2.4GHz", "5GHz")]
    switches = sum(1 for a, b in zip(bands, bands[1:], strict=False) if a != b)
    if switches >= 3:
        findings.append({"level": "warn", "title": "Passa di continuo fra 2.4 e 5 GHz",
                         "text": f"{switches} cambi di banda: al bordo della copertura del 5 GHz il dispositivo "
                                 "salta da una banda all'altra.",
                         "fix": "Se è attivo il band steering prova a spegnerlo, oppure migliora il 5 GHz "
                                "in quella stanza."})
    if len(roams) >= 6:
        froms = {(r.get("info") or "")[3:] for r in roams if (r.get("info") or "").startswith("da ")}
        aps = sorted({r["ap"] for r in roams} | froms)
        findings.append({"level": "warn", "title": "Rimbalza fra gli access point",
                         "text": f"{len(roams)} spostamenti fra {', '.join(a for a in aps if a)}.",
                         "fix": "Due AP coprono la stessa zona con segnale simile: abbassa la potenza di uno dei due."})
    if siblings >= 2:
        findings.append({"level": "warn", "title": "Cambia indirizzo MAC (indirizzo privato a rotazione)",
                         "text": f"Lo stesso nome è comparso con {siblings + 1} MAC diversi: a ogni ricollegamento "
                                 "chiede un nuovo indirizzo IP e può esaurire quelli liberi del DHCP.",
                         "fix": "Sul telefono: Impostazioni → Wi-Fi → (i) → Indirizzo Wi-Fi privato → Fisso."})
    if n >= 3 and not any(f["level"] == "bad" for f in findings[1:]) and by["other"] == n:
        findings.append({"level": "warn", "title": "Causa non evidente",
                         "text": "Segnale buono e nessuna riconfigurazione al momento dei distacchi: spesso è il "
                                 "risparmio energetico del dispositivo che si scollega da solo.",
                         "fix": "Se dà fastidio, prova a disattivare il risparmio Wi-Fi o l'indirizzo privato."})
    return {"stats": stats, "findings": findings, "timeline": list(reversed(detail_all(events, detail)))[:80]}


def detail_all(events: list[dict], drops: list[dict]) -> list[dict]:
    """Tutti gli eventi, con segnale e causa sugli scollegamenti."""
    by_id = {d["id"]: d for d in drops}
    return [by_id.get(e["id"], e) for e in events]


@router.get("/devices/{mac}/diagnosis")
def diagnosis(mac: str, hours: float = 24):
    hours = max(1.0, min(hours, 24 * 30))
    mac = mac.lower()
    since = int(time.time() - hours * 3600)
    with connect() as db:
        events = [dict(r) for r in db.execute(
            "SELECT id, ts, kind, ap, info FROM events WHERE mac = ? AND ts >= ? ORDER BY ts", (mac, since))]
        samples = [(r["ts"], r["rssi"]) for r in db.execute(
            "SELECT ts, rssi FROM rssi_samples WHERE mac = ? AND ts >= ? ORDER BY ts", (mac, since - 600))]
        config_times: dict[str, list[int]] = {}
        for r in db.execute("SELECT ts, ap FROM events WHERE kind = 'config' AND ts >= ?", (since - 600,)):
            config_times.setdefault(r["ap"], []).append(r["ts"])
        down_times: dict[str, list[int]] = {}
        for r in db.execute("SELECT ts, ap FROM events WHERE kind IN ('ap_down', 'ap_up') AND ts >= ?", (since - 600,)):
            down_times.setdefault(r["ap"], []).append(r["ts"])
        me = db.execute("SELECT hostname FROM devices WHERE mac = ?", (mac,)).fetchone()
        siblings = 0
        if me and me["hostname"]:
            siblings = db.execute("SELECT COUNT(*) FROM devices WHERE hostname = ? AND mac <> ? AND first_seen >= ?",
                                  (me["hostname"], mac, since)).fetchone()[0]

    def signal_at(ts: int) -> int | None:
        before = [v for t, v in samples if t <= ts]
        return before[-1] if before else None

    return analyse(events, signal_at, config_times, down_times, _kickout(), siblings, hours)
