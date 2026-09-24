"""Impostazioni del sito applicate a tutti gli AP via CLI, come le gestirebbe un controller cloud.

Ogni voce sa scrivere i comandi a partire dal valore voluto e leggere il valore attuale dalla running-config:
così il sistema applica le modifiche e, rileggendo la configurazione, riallinea gli AP che se ne allontanano.
I nomi dei profili (SSID1, SECURITY1, RADIO_SETTING_TYPE_2…) si ricavano dalla configurazione di ogni AP.
Solo comandi la cui sintassi compare nella running-config degli NWA50AX PRO (firmware V7.12).
"""
import re
from collections.abc import Callable
from dataclasses import dataclass, field


class RunningConfig:
    """Running-config divisa in blocchi: riga di intestazione → righe interne (indentate)."""

    def __init__(self, text: str):
        self.top: list[str] = []
        self.blocks: dict[str, list[str]] = {}
        cur: str | None = None
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.startswith("Router") or line.strip() == "!":
                cur = None if line.strip() == "!" else cur
                continue
            if line.startswith(" "):
                if cur is not None:
                    self.blocks[cur].append(line.strip())
            else:
                self.top.append(line)
                cur = line
                self.blocks.setdefault(line, [])

    def block(self, header: str) -> list[str]:
        return self.blocks.get(header, [])

    def value(self, header: str, prefix: str) -> str | None:
        for line in self.block(header):
            if line.startswith(prefix + " "):
                return line[len(prefix) + 1:]
        return None

    def has(self, header: str, line: str) -> bool:
        return line in self.block(header)

    # --- profili usati dall'AP ---
    def radio_profile(self, slot: int) -> str | None:
        v = self.value(f"wlan slot{slot}", "ap profile")
        return v.split()[0] if v else None

    def ssid_profile(self) -> str | None:
        """Profilo SSID della prima rete della 2.4 GHz (la rete principale)."""
        for line in self.block("wlan slot1"):
            if m := re.match(r"ssid profile 1 (\S+)", line):
                return m.group(1)
        return None

    def security_profile(self) -> str | None:
        p = self.ssid_profile()
        return self.value(f"wlan-ssid-profile {p}", "security") if p else None


@dataclass
class Item:
    key: str
    section: str                       # rete | radio | sistema
    label: str
    kind: str                          # text | int | bool | choice
    help: str = ""
    choices: list[str] = field(default_factory=list)
    unit: str = ""
    read: Callable[[RunningConfig], object] = lambda c: None
    build: Callable[[object, RunningConfig], list[str]] = lambda v, c: []
    per_ap: bool = False               # il valore dipende dall'AP (es. nome)
    enforce: bool = True               # False: si applica solo quando viene cambiata (es. password)


def _in_ssid(cfg: RunningConfig, *lines: str) -> list[str]:
    p = cfg.ssid_profile()
    return [f"wlan-ssid-profile {p}", *lines, "exit"] if p else []


def _in_security(cfg: RunningConfig, *lines: str) -> list[str]:
    p = cfg.security_profile()
    return [f"wlan-security-profile {p}", *lines, "exit"] if p else []


def _in_radios(cfg: RunningConfig, *lines: str) -> list[str]:
    out: list[str] = []
    for slot in (1, 2):
        if p := cfg.radio_profile(slot):
            out += [f"wlan-radio-profile {p}", *lines, "exit"]
    return out


def _rate(cfg: RunningConfig, direction: str) -> int | None:
    p = cfg.ssid_profile()
    v = cfg.value(f"wlan-ssid-profile {p}", f"{direction}-rate-limit") if p else None
    m = re.match(r"(\d+)", v or "")
    return int(m.group(1)) if m else None


def _ssid_flag(cfg: RunningConfig, line: str) -> bool:
    p = cfg.ssid_profile()
    return bool(p) and cfg.has(f"wlan-ssid-profile {p}", line)


def _sec_flag(cfg: RunningConfig, line: str) -> bool:
    p = cfg.security_profile()
    return bool(p) and cfg.has(f"wlan-security-profile {p}", line)


def _kickout(cfg: RunningConfig) -> int | None:
    p = cfg.radio_profile(1)
    if not p or not cfg.has(f"wlan-radio-profile {p}", "rssi-thres"):
        return 0                                   # 0 = disattivata
    v = cfg.value(f"wlan-radio-profile {p}", "rssi-kickout")
    return int(v) if v and re.fullmatch(r"-?\d+", v) else None


def _snmp_rw(cfg: RunningConfig) -> bool:
    return any(re.fullmatch(r"snmp-server community \S+ rw", line) for line in cfg.top)


def _snmp_rw_off(v, cfg: RunningConfig) -> list[str]:
    if v:            # True = scrittura consentita: non si aggiunge nulla, si lascia com'è
        return []
    return [f"no {line}" for line in cfg.top if re.fullmatch(r"snmp-server community \S+ rw", line)]


def _ntp(cfg: RunningConfig) -> str | None:
    for line in cfg.top:
        if line.startswith("ntp server "):
            return line.split()[2]
    return None


def _ntp_set(v, cfg: RunningConfig) -> list[str]:
    old = _ntp(cfg)
    return ([f"no ntp server {old}"] if old and old != v else []) + [f"ntp server {v}"]


def _lb(cfg: RunningConfig) -> bool:
    return "load-balancing slot1 activate" in cfg.top


def _lb_set(v, cfg: RunningConfig) -> list[str]:
    return [f"{'' if v else 'no '}load-balancing slot{s} activate" for s in (1, 2)]


MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def _blocked(cfg: RunningConfig) -> list[str]:
    """MAC nel profilo di blocco della rete principale (azione "deny")."""
    p = cfg.ssid_profile()
    prof = cfg.value(f"wlan-ssid-profile {p}", "macfilter") if p else None
    if not prof:
        return []
    return sorted(line.split()[0].lower() for line in cfg.block(f"wlan-macfilter-profile {prof}")
                  if MAC_RE.match(line.split()[0].lower()))


def _blocked_set(v, cfg: RunningConfig) -> list[str]:
    p = cfg.ssid_profile()
    prof = cfg.value(f"wlan-ssid-profile {p}", "macfilter") if p else None
    if not prof:
        return []
    want, have = set(v), set(_blocked(cfg))
    lines = [m for m in sorted(want - have)] + [f"no {m}" for m in sorted(have - want)]
    return [f"wlan-macfilter-profile {prof}", "filter-action deny", *lines, "exit"] if lines else []


def _psk(cfg: RunningConfig) -> str | None:
    p = cfg.security_profile()
    return cfg.value(f"wlan-security-profile {p}", "encrypted-wpa-psk") if p else None


def _security(cfg: RunningConfig) -> str | None:
    """wpa2 | wpa3 | wpa2/wpa3 (mode wpa3 + transition-mode) | altro valore della CLI."""
    p = cfg.security_profile()
    if not p:
        return None
    header = f"wlan-security-profile {p}"
    mode = cfg.value(header, "mode")
    if mode == "wpa3" and cfg.has(header, "transition-mode"):
        return "wpa2/wpa3"
    return mode


def _security_set(v, cfg: RunningConfig) -> list[str]:
    lines = {"wpa2": ["mode wpa2"], "wpa3": ["mode wpa3", "no transition-mode"],
             "wpa2/wpa3": ["mode wpa3", "transition-mode"]}[str(v)]
    return _in_security(cfg, *lines)


def _guest_slot_profile(cfg: RunningConfig) -> str | None:
    for line in cfg.block("wlan slot1"):
        if m := re.match(r"ssid profile 2 (\S+)", line):
            return m.group(1)
    return None


def _guest(cfg: RunningConfig) -> str | None:
    """Nome della rete ospiti se la seconda rete è attiva sugli slot, altrimenti "" (spenta)."""
    p = _guest_slot_profile(cfg)
    return (cfg.value(f"wlan-ssid-profile {p}", "ssid") or "") if p else ""


GUEST_SSID, GUEST_SEC = "SSID2", "SECURITY2"      # profili già creati da Nebula e non usati


def _guest_set(v, cfg: RunningConfig) -> list[str]:
    """Seconda rete isolata dalla LAN (guest-ssid), con la password della voce "guest_password"."""
    from .site_config import load     # import qui: site_config importa questo modulo
    name = str(v or "").strip()
    slots = [s for s in (1, 2) if f"wlan slot{s}" in cfg.blocks]
    if not name:
        return [x for s in slots for x in (f"wlan slot{s}", "no ssid profile 2", "exit")]
    password = load().get("guest_password")
    sec = ["mode wpa2", f"wpa-psk {password}"] if password else ["mode none"]
    return [
        f"wlan-security-profile {GUEST_SEC}", *sec, "exit",
        f"wlan-ssid-profile {GUEST_SSID}", f"ssid {name}", f"security {GUEST_SEC}", "guest-ssid", "exit",
        *[x for s in slots for x in (f"wlan slot{s}", f"ssid profile 2 {GUEST_SSID}", "exit")],
    ]


ITEMS: list[Item] = [
    # --- rete Wi-Fi principale ---
    Item("ssid_name", "rete", "Nome della rete (SSID)", "text",
         "Cambiarlo scollega tutti i dispositivi: vanno ricollegati alla rete con il nuovo nome.",
         read=lambda c: c.value(f"wlan-ssid-profile {c.ssid_profile()}", "ssid") if c.ssid_profile() else None,
         build=lambda v, c: _in_ssid(c, f"ssid {v}")),
    Item("wifi_password", "rete", "Password della rete", "password",
         "Da 8 a 63 caratteri. Cambiarla scollega tutti i dispositivi: vanno ricollegati con la nuova password.",
         enforce=False, read=_psk, build=lambda v, c: _in_security(c, f"wpa-psk {v}")),
    Item("security_mode", "rete", "Sicurezza", "choice",
         "WPA2+WPA3 è il più compatibile. Solo WPA3 esclude i dispositivi più vecchi, che non si collegano più.",
         choices=["wpa2", "wpa2/wpa3", "wpa3"], read=_security, build=_security_set),
    Item("guest_name", "ospiti", "Nome della rete ospiti", "text",
         "Seconda rete isolata dalla casa: gli ospiti navigano ma non vedono i tuoi dispositivi. Vuoto = spenta.",
         read=_guest, build=_guest_set),
    Item("guest_password", "ospiti", "Password della rete ospiti", "password",
         "Da 8 a 63 caratteri; senza password la rete ospiti è aperta.", enforce=False, read=lambda c: None,
         build=lambda v, c: [f"wlan-security-profile {GUEST_SEC}", "mode wpa2", f"wpa-psk {v}", "exit"]
         if _guest_slot_profile(c) else []),
    Item("ssid_hidden", "rete", "Rete nascosta", "bool",
         "Il nome della rete non compare negli elenchi: per collegarsi va scritto a mano.",
         read=lambda c: _ssid_flag(c, "hide"),
         build=lambda v, c: _in_ssid(c, "hide" if v else "no hide")),
    Item("mac_block", "rete", "Dispositivi bloccati (MAC)", "list",
         "Un indirizzo MAC per riga: questi dispositivi non possono collegarsi alla rete.",
         read=_blocked, build=_blocked_set),
    Item("rate_down", "rete", "Limite di download per dispositivo", "int",
         "0 = nessun limite.", unit="kbps", read=lambda c: _rate(c, "downlink"),
         build=lambda v, c: _in_ssid(c, f"downlink-rate-limit {v} kbps")),
    Item("rate_up", "rete", "Limite di upload per dispositivo", "int",
         "0 = nessun limite.", unit="kbps", read=lambda c: _rate(c, "uplink"),
         build=lambda v, c: _in_ssid(c, f"uplink-rate-limit {v} kbps")),
    Item("dot11kv", "rete", "Roaming assistito (802.11k/v)", "bool",
         "Gli AP suggeriscono ai dispositivi l'AP migliore a cui passare.",
         read=lambda c: _ssid_flag(c, "dot11k-v activate"),
         build=lambda v, c: _in_ssid(c, "dot11k-v activate" if v else "no dot11k-v activate")),
    Item("dot11r", "rete", "Roaming veloce (802.11r)", "bool",
         "Passaggio fra AP senza ripetere l'autenticazione. Pochi dispositivi vecchi non lo supportano.",
         read=lambda c: _sec_flag(c, "dot11r activate"),
         build=lambda v, c: _in_security(c, "dot11r activate" if v else "no dot11r activate")),
    # --- radio ---
    Item("rssi_kickout", "radio", "Espulsione dei segnali deboli", "choice",
         "Stacca i dispositivi sotto questa soglia, così si agganciano all'AP più vicino. 0 = disattivata.",
         choices=["0", "-65", "-70", "-75", "-80", "-85"], unit="dBm", read=_kickout,
         build=lambda v, c: _in_radios(c, "no rssi-thres") if int(v) == 0
         else _in_radios(c, "rssi-thres", f"rssi-kickout {v}")),
    Item("load_balancing", "radio", "Bilanciamento del carico", "bool",
         "Distribuisce i dispositivi fra le radio quando un AP è troppo affollato.",
         read=_lb, build=_lb_set),
    # --- sistema ---
    Item("led_off", "sistema", "LED spenti", "bool", "Utile per gli AP in camera da letto.",
         read=lambda c: "led_suppress enable" in c.top,
         build=lambda v, c: ["led_suppress enable" if v else "led_suppress disable"]),
    Item("snmp_rw", "sistema", "SNMP in scrittura", "bool",
         "Consente di modificare l'AP via SNMP con la community: meglio spento, la dashboard legge soltanto.",
         read=_snmp_rw, build=_snmp_rw_off),
    Item("ntp_server", "sistema", "Server dell'ora (NTP)", "text", "Es. time.google.com o l'IP di OPNsense.",
         read=_ntp, build=_ntp_set),
    Item("hostname_sync", "sistema", "Nome dell'AP uguale a quello della dashboard", "bool",
         "Imposta l'hostname di ogni AP con il nome usato qui (es. SOGGIORNO).", per_ap=True,
         read=lambda c: None, build=lambda v, c: []),
]

BY_KEY = {i.key: i for i in ITEMS}


def hostname_commands(name: str, cfg: RunningConfig) -> list[str]:
    host = re.sub(r"[^A-Za-z0-9-]", "-", name).strip("-")[:32] or "AP"
    current = next((line.split(None, 1)[1] for line in cfg.top if line.startswith("hostname ")), None)
    return [] if current == host else [f"hostname {host}"]


def parse_value(item: Item, raw) -> object:
    """Valore dal pannello → tipo dell'impostazione (ValueError se non valido)."""
    if item.kind == "bool":
        return bool(raw)
    if item.kind == "list":
        items = raw if isinstance(raw, list) else str(raw).replace(",", "\n").split()
        macs = sorted({m.strip().lower().replace("-", ":") for m in items if m.strip()})
        bad = [m for m in macs if not MAC_RE.match(m)]
        if bad:
            raise ValueError(f"MAC non valido: {bad[0]}")
        return macs
    if item.kind == "password":
        s = str(raw)
        if not 8 <= len(s) <= 63 or any(ch in s for ch in "\n\r\t") or s != s.strip():
            raise ValueError("da 8 a 63 caratteri, senza spazi iniziali o finali")
        return s
    if item.kind == "int":
        v = int(raw)
        if not 0 <= v <= 10_000_000:
            raise ValueError("fuori intervallo")
        return v
    s = str(raw).strip()
    if item.kind == "choice" and s not in item.choices:
        raise ValueError("scelta non valida")
    if item.kind == "text" and item.key == "guest_name" and s == "":
        return s                                   # nome vuoto = rete ospiti spenta
    if item.kind == "text":
        if not s or len(s) > 32 or not re.fullmatch(r"[\w .@:\-]+", s):
            raise ValueError("testo non valido (max 32 caratteri, niente simboli speciali)")
    return s


def same(item: Item, want, have) -> bool:
    if have is None:
        return False
    if item.kind == "list":
        return sorted(want or []) == sorted(have or [])
    if item.kind in ("int", "choice"):
        try:
            return int(want) == int(have)
        except (TypeError, ValueError):
            return False
    return str(want) == str(have) if item.kind == "text" else bool(want) == bool(have)
