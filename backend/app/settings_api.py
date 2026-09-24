"""Pannello impostazioni: access point (aggiungi, modifica, elimina, prova, rileva) e OPNsense."""
import asyncio
import ipaddress
import re
import ssl
import time
import urllib.error
from dataclasses import asdict, replace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import poller
from .collectors import opnsense, ssh
from .core import store
from .core.config import EDITABLE, get_settings
from .core.security import current_user

router = APIRouter(prefix="/api/settings", dependencies=[Depends(current_user)])

HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.\-]{0,251}[A-Za-z0-9])?$")


class ApIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    host: str = Field(min_length=1, max_length=253)
    method: Literal["snmp", "ssh"]
    enabled: bool = True
    snmp_version: Literal["1", "2c", "3"] = "2c"
    snmp_community: str = ""
    snmp_user: str = ""
    snmp_auth_proto: Literal["MD5", "SHA", "SHA-224", "SHA-256", "SHA-384", "SHA-512"] = "SHA"
    snmp_auth_pass: str = ""
    snmp_priv_proto: Literal["DES", "AES", "AES-192", "AES-256"] = "AES"
    snmp_priv_pass: str = ""
    ssh_port: int = Field(22, ge=1, le=65535)
    ssh_user: str = ""
    ssh_password: str = ""
    id: int | None = None          # per provare un AP salvato con le sue password
    copy_from: int | None = None   # nuovo AP: password prese da questo AP se lasciate vuote
    apply_to_all: bool = False     # copia le credenziali su tutti gli AP con lo stesso protocollo

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Il nome è obbligatorio")
        return v.strip()

    @field_validator("host")
    @classmethod
    def _host(cls, v: str) -> str:
        v = v.strip()
        try:
            ipaddress.ip_address(v)
        except ValueError:
            if not HOST_RE.match(v):
                raise ValueError("Indirizzo non valido: usa un IP o un nome host") from None
        return v


def _merge(body: ApIn, ap_id: int | None) -> store.ApConfig:
    """Le password lasciate vuote restano quelle salvate (o quelle dell'AP da cui si copia)."""
    data = body.model_dump(exclude={"id", "copy_from", "apply_to_all"})
    src_id = ap_id if ap_id is not None else (body.id or body.copy_from)
    src = store.get_ap(src_id) if src_id else None
    if src:
        for k in store.SECRETS:
            if not data[k]:
                data[k] = getattr(src, k)
    ap = store.ApConfig(id=ap_id, **data)
    if ap.method == "snmp" and ap.snmp_version == "3":
        if not ap.snmp_user:
            raise HTTPException(422, "SNMP v3: l'utente è obbligatorio")
        if ap.snmp_auth_pass and len(ap.snmp_auth_pass) < 8:
            raise HTTPException(422, "SNMP v3: la password di autenticazione deve avere almeno 8 caratteri")
        if ap.snmp_priv_pass and not ap.snmp_auth_pass:
            raise HTTPException(422, "SNMP v3: la cifratura richiede anche la password di autenticazione")
    if ap.method == "ssh" and not ap.ssh_user:
        raise HTTPException(422, "SSH: l'utente è obbligatorio")
    return ap


def _public(ap: store.ApConfig) -> dict:
    d = asdict(ap)
    for k in store.SECRETS:
        d[f"has_{k}"] = bool(d.pop(k))
    return d


def _hint(ap: store.ApConfig, error: str | None) -> str | None:
    """Suggerimento pratico a partire dall'errore del collector."""
    if not error:
        return None
    e = error.lower()
    if ap.method == "snmp":
        if "non installati" in e:
            return "Installa net-snmp sul server; nell'immagine Docker è già incluso."
        if "unknown user" in e or "authentication failure" in e or "wrong digest" in e:
            return "Utente o password SNMPv3 errati, oppure protocollo di autenticazione/cifratura diverso."
        if "timeout" in e or "no response" in e:
            return ("L'AP non risponde in SNMP. In Nebula (Site-wide → Configure → General settings → SNMP access) "
                    "controlla che SNMP sia attivo, che versione e community/utente coincidano e che l'IP di questo "
                    "server sia tra quelli ammessi. Gli NWA50AX PRO non attivano SNMP: usa SSH.")
        return None
    if "rifiutata" in e:
        return ("Password errata. Dopo troppi tentativi l'AP blocca l'IP del server anche con la password giusta: "
                "in quel caso riavvialo da Nebula.")
    if "non impostata" in e:
        return "Usa utente e password delle Local credentials di Nebula (Site-wide → Configure → General settings)."
    if "refused" in e:
        return "La porta SSH è chiusa: controlla il numero di porta."
    if "timed out" in e or "timeout" in e or "unreachable" in e or "no route" in e:
        return "L'AP non è raggiungibile da questo server: controlla l'indirizzo e che sia acceso."
    return None


# ---------- access point ----------
@router.get("/aps")
def list_aps():
    return [_public(a) for a in store.list_aps()]


def _saved(ap: store.ApConfig, apply_to_all: bool) -> dict:
    copied = store.copy_credentials(ap) if apply_to_all else 0
    poller.poll_now()
    return {**_public(ap), "copied": copied}


@router.post("/aps", status_code=201)
def create_ap(body: ApIn):
    ap = _merge(body, None)
    if msg := store.conflict(ap):
        raise HTTPException(409, msg)
    ap.id = store.save_ap(ap)
    return _saved(ap, body.apply_to_all)


@router.put("/aps/{ap_id}")
def update_ap(ap_id: int, body: ApIn):
    old = store.get_ap(ap_id)
    if not old:
        raise HTTPException(404, "Access point non trovato")
    ap = _merge(body, ap_id)
    if msg := store.conflict(ap):
        raise HTTPException(409, msg)
    store.save_ap(ap)
    if old.name != ap.name:
        store.rename_history(old.name, ap.name)
    return _saved(ap, body.apply_to_all)


@router.delete("/aps/{ap_id}")
def delete_ap(ap_id: int):
    ap = store.get_ap(ap_id)
    if not ap:
        raise HTTPException(404, "Access point non trovato")
    store.delete_ap(ap)
    poller.poll_now()
    return {"ok": True}


@router.post("/aps/test")
async def test_ap(body: ApIn):
    """Una lettura di prova con i dati del modulo, senza salvare."""
    ap = _merge(body, None)
    started = time.monotonic()
    r = await poller.read_ap(ap)
    return {
        "online": r.online, "model": r.model, "firmware": r.firmware, "uptime_s": r.uptime_s,
        "clients": len(r.clients), "traffic": bool(r.traffic), "error": r.error,
        "hint": _hint(ap, r.error), "ms": round((time.monotonic() - started) * 1000),
    }


@router.get("/aps/{ap_id}/raw")
def raw_output(ap_id: int):
    """Ultimo output della CLI SSH così com'è: serve a riconoscere i formati non ancora gestiti."""
    ap = store.get_ap(ap_id)
    if not ap:
        raise HTTPException(404, "Access point non trovato")
    ts, text = ssh.last_output.get(ap.host, (None, ""))
    return {"ts": ts, "text": text}


async def _port_open(host: str, port: int, timeout: float = 3) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (OSError, TimeoutError):
        return False
    writer.close()
    return True


@router.post("/aps/detect")
async def detect_ap(body: ApIn):
    """Prova SNMP (con le credenziali del modulo, o community `public`) e la porta SSH, e consiglia."""
    ap = _merge(body, None)
    default_community = ap.snmp_version != "3" and not ap.snmp_community
    probe = replace(ap, method="snmp", snmp_community=ap.snmp_community or "public")
    ssh_open, reading = await asyncio.gather(_port_open(ap.host, ap.ssh_port), poller.read_ap(probe))
    if reading.online:
        suggested = "snmp"
        message = (f"Risponde in SNMP{f' ({reading.model})' if reading.model else ''}: consigliato, "
                   "fornisce anche traffico, canali e firmware.")
    elif ssh_open:
        suggested = "ssh"
        message = ("SNMP non risponde ma SSH è aperto: usa SSH (tipico degli NWA50AX PRO, dove Nebula non attiva "
                   "SNMP). Il traffico per SSID non sarà disponibile.")
    else:
        suggested = None
        message = ("Né SNMP né SSH rispondono: controlla l'indirizzo, che l'AP sia acceso e che questo server "
                   "sia nella stessa rete.")
    return {
        "suggested": suggested, "snmp_ok": reading.online, "ssh_open": ssh_open, "model": reading.model,
        "used_default_community": default_community and reading.online, "message": message,
    }


# ---------- OPNsense e raccolta ----------
class GeneralIn(BaseModel):
    opnsense_url: str = ""
    opnsense_key: str = ""
    opnsense_secret: str = ""        # vuoto = invariato
    opnsense_verify_tls: bool = True
    opnsense_wan_if: str = "wan"
    local_domain: str = ""
    poll_interval: int = Field(60, ge=15, le=3600)
    retention_days: int = Field(30, ge=1, le=365)

    @field_validator("opnsense_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if v and not re.match(r"^https?://", v):
            raise ValueError("L'indirizzo di OPNsense deve iniziare con https:// (o http://)")
        return v

    @field_validator("opnsense_key", "opnsense_wan_if", "local_domain")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


def _general() -> dict:
    s = get_settings()
    d = {k: getattr(s, k) for k in EDITABLE if k != "opnsense_secret"}
    d["has_opnsense_secret"] = bool(s.opnsense_secret)
    return d


@router.get("/general")
def get_general():
    return _general()


@router.put("/general")
def save_general(body: GeneralIn):
    data = body.model_dump()
    if not data["opnsense_secret"]:
        data.pop("opnsense_secret")
    store.set_settings(data)
    poller.poll_now()
    return _general()


@router.post("/opnsense/test")
async def test_opnsense(body: GeneralIn):
    """Prova le impostazioni del modulo: accesso all'API e interfaccia WAN."""
    s = get_settings()
    cfg = s.model_copy(update={
        "opnsense_url": body.opnsense_url, "opnsense_key": body.opnsense_key,
        "opnsense_secret": body.opnsense_secret or s.opnsense_secret,
        "opnsense_verify_tls": body.opnsense_verify_tls,
    })
    if not (cfg.opnsense_url and cfg.opnsense_key and cfg.opnsense_secret):
        return {"ok": False, "message": "Compila indirizzo, chiave e secret API."}
    try:
        gws, ifaces = await asyncio.gather(
            asyncio.to_thread(opnsense.fetch, "routes/gateway/status", cfg, 10),
            asyncio.to_thread(opnsense.fetch, "diagnostics/traffic/interface", cfg, 10),
        )
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"ok": False, "message": "Chiave o secret errati, oppure l'utente API non ha i permessi."}
        return {"ok": False, "message": f"OPNsense ha risposto {exc.code}: controlla l'indirizzo."}
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            return {"ok": False, "message": "Certificato non verificabile: se è autofirmato togli la spunta "
                                            "“Verifica certificato”."}
        return {"ok": False, "message": f"Non raggiungibile ({exc.reason}). Se OPNsense è dietro un reverse proxy "
                                        "usa il nome host, non l'IP."}
    except Exception as exc:
        return {"ok": False, "message": f"Risposta non valida: {exc}"}
    names = [g.get("name") for g in gws.get("items", [])]
    available = sorted((ifaces.get("interfaces") or {}).keys())
    message = f"Collegato: {len(names)} gateway ({', '.join(filter(None, names)) or '—'})."
    if body.opnsense_wan_if not in available:
        return {"ok": False, "message": f"{message} Ma l'interfaccia WAN “{body.opnsense_wan_if}” non esiste: "
                                        f"scegli fra {', '.join(available)}."}
    return {"ok": True, "message": f"{message} Interfaccia WAN “{body.opnsense_wan_if}” trovata."}
