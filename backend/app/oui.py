"""Produttore dal MAC: elenco pubblico IEEE (oui.csv) scaricato nell'immagine Docker in fase di build.

Senza il file si riconoscono solo i MAC privati (randomizzati da iOS/Android/Windows): il loro prefisso
non appartiene a nessun produttore, quindi non si inventa un nome.
"""
import csv
import logging
import os
from functools import lru_cache
from pathlib import Path

from .devices import is_private_mac

log = logging.getLogger("oui")

PRIVATE = "MAC privato"
# cercato in quest'ordine: variabile d'ambiente, accanto al codice (immagine Docker), accanto al DB
_CANDIDATES = (os.environ.get("OUI_PATH", ""), str(Path(__file__).resolve().parent.parent / "oui.csv"), "data/oui.csv")


def _clean(name: str) -> str:
    """"Apple, Inc." → "Apple": via le forme societarie che allungano la colonna senza aggiungere nulla."""
    name = " ".join(name.split())
    for suffix in (", Inc.", " Inc.", " Inc", ", Ltd.", " Co.,Ltd", " Co., Ltd.", " Co.,Ltd.", " Corporation",
                   " Corp.", " GmbH", " S.p.A.", " SpA", " Limited", " LLC", " Technologies", " Technology"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].rstrip(" ,")
    return name


@lru_cache(maxsize=1)
def table() -> dict[str, str]:
    for path in filter(None, _CANDIDATES):
        p = Path(path)
        if not p.is_file():
            continue
        out: dict[str, str] = {}
        with p.open(encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                prefix = (row.get("Assignment") or "").strip().lower()
                org = (row.get("Organization Name") or "").strip()
                if len(prefix) == 6 and org:
                    out[prefix] = _clean(org)
        log.info("elenco produttori caricato da %s: %d prefissi", p, len(out))
        return out
    return {}


def vendor(mac: str | None) -> str | None:
    if not mac:
        return None
    if is_private_mac(mac):
        return PRIVATE
    return table().get(mac.replace(":", "").replace("-", "").lower()[:6])
