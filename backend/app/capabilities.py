"""Cosa sa fare ogni modello di AP, per non proporre (né inviare) impostazioni che non supporta.

Il modello si legge dall'ultimo stato salvato (show version / SNMP). Le larghezze sono quelle che Nebula
propone per ciascun modello: gli AP Wi-Fi 5 si fermano a 80 MHz sulla 5 GHz, i Wi-Fi 6 arrivano a 160.
Un modello sconosciuto ha le capacità minime comuni, così non si propone mai qualcosa di troppo.
"""
import json
import re

from .core.db import connect

WIDTHS_WIFI5 = {"2.4GHz": ["20", "20/40"], "5GHz": ["20", "20/40", "20/40/80"]}
WIDTHS_WIFI6 = {"2.4GHz": ["20", "20/40"], "5GHz": ["20", "20/40", "20/40/80", "20/40/80/160"]}


# scelte ammesse per voce, per generazione: il WPA3 è obbligatorio solo dal Wi-Fi 6
CHOICES_WIFI5 = {"security_mode": ["wpa2"]}
CHOICES_WIFI6 = {"security_mode": ["wpa2", "wpa2/wpa3", "wpa3"]}
# voci che si possono attivare anche se l'AP oggi non le ha nella configurazione (le crea il comando)
CREATABLE = {"guest_name", "guest_password", "wifi_schedule", "mac_block", "ntp_server", "wifi_password"}


def generation(model: str | None) -> int | None:
    """7 per i modelli "BE" (NWA50BE, WBE660S…), 6 per gli "AX", 5 per gli "AC"/WAC, None se non è noto."""
    m = (model or "").upper()
    if not m:
        return None
    if "BE" in m.replace("-", ""):
        return 7
    if "AX" in m:
        return 6
    return 5


def of_model(model: str | None) -> dict:
    gen = generation(model)
    # Wi-Fi 7 sulle bande 2.4/5 GHz ha le stesse larghezze e la stessa sicurezza del Wi-Fi 6
    modern = gen is not None and gen >= 6
    return {"model": model, "wifi": gen, "widths": WIDTHS_WIFI6 if modern else WIDTHS_WIFI5,
            "choices": CHOICES_WIFI6 if modern else CHOICES_WIFI5}


def models() -> dict[str, str | None]:
    with connect() as db:
        return {r["ap"]: r["model"] for r in db.execute("SELECT ap, model FROM ap_status")}


def of_ap(name: str) -> dict:
    """Capacità del modello, ristrette alle larghezze che l'AP ha dichiarato con Esplora comandi."""
    caps = of_model(models().get(name))
    said = learned_widths(name)
    if said:
        caps["widths"] = {b: [w for w in ws if w in said] or ws for b, ws in caps["widths"].items()}
    return caps


# risposta a "ch-width ?": qualche riga dopo l'eco compare "<20, 20/40, 20/40/80>"
WIDTH_HELP = re.compile(r"ch-width[^<]{0,80}<([0-9/, ]+)>")


def parse_widths(help_text: str) -> list[str]:
    """Larghezze dall'aiuto di "ch-width ?": "<20, 20/40, 20/40/80>" → ["20", "20/40", "20/40/80"]."""
    m = WIDTH_HELP.search(help_text)
    return [w.strip() for w in m.group(1).split(",") if w.strip()] if m else []


def learned_widths(ap_name: str) -> list[str]:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (f"caps_widths:{ap_name}",)).fetchone()
    return json.loads(row["value"]) if row else []


def fit_width(width: str, band: str, caps: dict) -> str:
    """La larghezza richiesta se il modello la supporta, altrimenti la più ampia che supporta."""
    allowed = caps["widths"][band]
    return width if width in allowed else allowed[-1]


def fit_item(key: str, value, caps: dict):
    """Il valore del sito adattato al modello: una scelta non ammessa diventa la più alta ammessa."""
    allowed = caps["choices"].get(key)
    if allowed and isinstance(value, str) and value not in allowed:
        return allowed[-1]
    return value


# voci che un AP supporta solo se l'ha dichiarato lui: frase dell'aiuto della CLI ("?") letta con Esplora comandi
HELP_SIGNS = {"min_rate_24": "2.4G Minimum rate control"}
# valore che l'AP usa quando la voce non compare nella configurazione
DEFAULTS = {"min_rate_24": "1"}


def learn(ap_name: str, help_text: str) -> list[str]:
    """Salva le voci che l'AP ha dichiarato di supportare nell'output di Esplora comandi."""
    found = sorted(learned(ap_name) | {k for k, sign in HELP_SIGNS.items() if sign in help_text})
    widths = parse_widths(help_text)
    with connect() as db:
        if widths:
            db.execute("INSERT INTO settings(key, value) VALUES (?,?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                       (f"caps_widths:{ap_name}", json.dumps(widths)))
        db.execute("INSERT INTO settings(key, value) VALUES (?,?) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (f"caps:{ap_name}", json.dumps(found)))
    return found


def learned(ap_name: str) -> set[str]:
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (f"caps:{ap_name}",)).fetchone()
    return set(json.loads(row["value"])) if row else set()


def current(key: str, value, ap_name: str):
    """Valore da mostrare: quello letto, o quello predefinito se l'AP supporta la voce ma non la elenca."""
    if value is None and key in DEFAULTS and key in learned(ap_name):
        return DEFAULTS[key]
    return value


def available(key: str, current, kind: str, ap_name: str | None = None) -> bool:
    """Un AP "ha" una voce se la sua configurazione la contiene (la password si scrive anche se non si legge)
    o se l'ha dichiarata nell'aiuto della CLI."""
    if key in HELP_SIGNS:
        return current is not None or (ap_name is not None and key in learned(ap_name))
    return current is not None or kind == "password" or key in CREATABLE
