"""Cosa sa fare ogni modello di AP, per non proporre (né inviare) impostazioni che non supporta.

Il modello si legge dall'ultimo stato salvato (show version / SNMP). Le larghezze sono quelle che Nebula
propone per ciascun modello: gli AP Wi-Fi 5 si fermano a 80 MHz sulla 5 GHz, i Wi-Fi 6 arrivano a 160.
Un modello sconosciuto ha le capacità minime comuni, così non si propone mai qualcosa di troppo.
"""
from .core.db import connect

WIDTHS_WIFI5 = {"2.4GHz": ["20", "20/40"], "5GHz": ["20", "20/40", "20/40/80"]}
WIDTHS_WIFI6 = {"2.4GHz": ["20", "20/40"], "5GHz": ["20", "20/40", "20/40/80", "20/40/80/160"]}


# scelte ammesse per voce, per generazione: il WPA3 è obbligatorio solo dal Wi-Fi 6
CHOICES_WIFI5 = {"security_mode": ["wpa2"]}
CHOICES_WIFI6 = {"security_mode": ["wpa2", "wpa2/wpa3", "wpa3"]}
# voci che si possono attivare anche se l'AP oggi non le ha nella configurazione (le crea il comando)
CREATABLE = {"guest_name", "guest_password", "wifi_schedule", "mac_block", "ntp_server", "wifi_password"}


def generation(model: str | None) -> int | None:
    """6 per i modelli "AX" (Wi-Fi 6), 5 per gli "AC"/WAC, None se il modello non è noto."""
    m = (model or "").upper()
    if not m:
        return None
    if "AX" in m:
        return 6
    return 5


def of_model(model: str | None) -> dict:
    gen = generation(model)
    return {"model": model, "wifi": gen, "widths": WIDTHS_WIFI6 if gen == 6 else WIDTHS_WIFI5,
            "choices": CHOICES_WIFI6 if gen == 6 else CHOICES_WIFI5}


def models() -> dict[str, str | None]:
    with connect() as db:
        return {r["ap"]: r["model"] for r in db.execute("SELECT ap, model FROM ap_status")}


def of_ap(name: str) -> dict:
    return of_model(models().get(name))


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


def available(key: str, current, kind: str) -> bool:
    """Un AP "ha" una voce se la sua configurazione la contiene (la password si scrive anche se non si legge)."""
    return current is not None or kind == "password" or key in CREATABLE
