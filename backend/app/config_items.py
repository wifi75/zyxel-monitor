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


def _in_radio(cfg: RunningConfig, slot: int, *lines: str) -> list[str]:
    p = cfg.radio_profile(slot)
    return [f"wlan-radio-profile {p}", *lines, "exit"] if p else []


def _radio_value(cfg: RunningConfig, slot: int, prefix: str) -> str | None:
    p = cfg.radio_profile(slot)
    return cfg.value(f"wlan-radio-profile {p}", prefix) if p else None


def _radio_flag(cfg: RunningConfig, slot: int, line: str) -> bool | None:
    """Voce senza valori nel profilo radio: presente = attiva; None se l'AP non ha il profilo."""
    p = cfg.radio_profile(slot)
    return cfg.has(f"wlan-radio-profile {p}", line) if p else None


def _rate(cfg: RunningConfig, direction: str) -> int | None:
    p = cfg.ssid_profile()
    v = cfg.value(f"wlan-ssid-profile {p}", f"{direction}-rate-limit") if p else None
    m = re.match(r"(\d+)", v or "")
    return int(m.group(1)) if m else None


def _ssid_value(cfg: RunningConfig, prefix: str) -> str | None:
    p = cfg.ssid_profile()
    return cfg.value(f"wlan-ssid-profile {p}", prefix) if p else None


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
    if not p:
        return None
    header = f"wlan-security-profile {p}"
    # firmware 7.x: "encrypted-wpa-psk" (cifrata); firmware 6.x: "wpa-psk" in chiaro. Il valore non esce mai
    # dal server: l'API dice solo se la password è impostata.
    return cfg.value(header, "encrypted-wpa-psk") or cfg.value(header, "wpa-psk")


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


DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# preset del riavvio programmato: giorni attivi e ora
REBOOT_PRESETS = {"daily-04": (DAYS, "04:00"), "sun-04": (("sun",), "04:00"), "sat-04": (("sat",), "04:00")}


def _reboot(cfg: RunningConfig) -> str | None:
    lines = cfg.block("schedule-reboot")
    if not lines or "activate" not in lines:
        return "off"
    days = tuple(d for d in DAYS if d in lines)
    time_ = next((line.split()[1] for line in lines if line.startswith("reboot-time ")), None)
    for key, (d, t) in REBOOT_PRESETS.items():
        if set(d) == set(days) and t == time_:
            return key
    return "custom"


def _reboot_set(v, cfg: RunningConfig) -> list[str]:
    if v == "off":
        return ["schedule-reboot", "no activate", "exit"]
    days, time_ = REBOOT_PRESETS[str(v)]
    day_lines = [d if d in days else f"no {d}" for d in DAYS]
    return ["schedule-reboot", *day_lines, f"reboot-time {time_}", "activate", "exit"]


HHMM = r"(?:[01]\d|2[0-3]):[0-5]\d"
SCHEDULE_RE = re.compile(rf"^({HHMM})-({HHMM})$")


def _schedule(cfg: RunningConfig) -> str | None:
    """Fascia in cui la rete è accesa ("07:00-23:00"), "" se sempre accesa. Letta dal lunedì."""
    p = cfg.ssid_profile()
    if not p:
        return None
    header = f"wlan-ssid-profile {p}"
    v = cfg.value(header, "mon enable")
    if cfg.has(header, "ssid-schedule"):            # firmware 7.x: "ssid-schedule" + "mon enable 07:00 23:00"
        parts = (v or "").split()
        return f"{parts[0]}-{parts[1]}" if len(parts) == 2 else "custom"
    if v and SCHEDULE_RE.match(v):                   # firmware 6.x: "mon enable 04:00-22:00" nel profilo
        return v
    return ""


def _old_schedule_syntax(cfg: RunningConfig) -> bool:
    """Firmware 6.x: gli orari stanno nel profilo SSID come "mon enable HH:MM-HH:MM", senza "ssid-schedule"."""
    return any(SCHEDULE_RE.match(line.split(" enable ", 1)[-1]) for h, lines in cfg.blocks.items()
               if h.startswith("wlan-ssid-profile") for line in lines if " enable " in line)


def _schedule_set(v, cfg: RunningConfig) -> list[str]:
    if _old_schedule_syntax(cfg):
        return []       # sintassi 6.x per scrivere gli orari non verificata: si legge soltanto, non si inventa
    if not v:
        return _in_ssid(cfg, "no ssid-schedule")
    start, end = SCHEDULE_RE.match(str(v)).groups()
    return _in_ssid(cfg, "ssid-schedule", *[f"{d} enable {start} {end}" for d in DAYS])


SSID_5G = "SSID5G"


def _slot_ssid(c: RunningConfig, slot: int) -> str | None:
    for line in c.block(f"wlan slot{slot}"):
        if m := re.match(r"ssid profile 1 (\S+)", line):
            return m.group(1)
    return None


def _ssid_5g(c: RunningConfig) -> str | None:
    """Nome della rete sulla 5 GHz (uguale a quello della 2.4 GHz se le bande condividono il profilo)."""
    p5 = _slot_ssid(c, 2)
    return c.value(f"wlan-ssid-profile {p5}", "ssid") if p5 else None


def _ssid_5g_set(v: object, c: RunningConfig) -> list[str]:
    """Nome separato: copia del profilo 2.4 GHz (stessa password e opzioni) col nome nuovo, sulla 5 GHz."""
    p2 = c.ssid_profile()
    if not p2 or not _slot_ssid(c, 2):
        return []
    if not v:
        return []
    if v == c.value(f"wlan-ssid-profile {p2}", "ssid"):          # stesso nome: una rete sola sulle due bande
        return [] if _slot_ssid(c, 2) == p2 else ["wlan slot2", f"ssid profile 1 {p2}", "exit"]
    if _slot_ssid(c, 2) == SSID_5G:                              # già separata: cambia solo il nome
        return [f"wlan-ssid-profile {SSID_5G}", f"ssid {v}", "exit"]
    body = [x for x in c.block(f"wlan-ssid-profile {p2}") if not x.startswith("ssid ") and x != "ssid-schedule"]
    return [f"wlan-ssid-profile {SSID_5G}", f"ssid {v}", *body, "exit",
            "wlan slot2", f"ssid profile 1 {SSID_5G}", "exit"]


ITEMS: list[Item] = [
    # --- rete Wi-Fi principale ---
    Item("ssid_name", "rete", "Nome rete 2.4 GHz (SSID)", "text",
         "Se la 5 GHz ha lo stesso nome è un'unica rete e cambia anche lei. "
         "Cambiarlo scollega i dispositivi: vanno ricollegati col nuovo nome.",
         read=lambda c: c.value(f"wlan-ssid-profile {c.ssid_profile()}", "ssid") if c.ssid_profile() else None,
         build=lambda v, c: _in_ssid(c, f"ssid {v}")),
    Item("ssid_5g", "rete", "Nome rete 5 GHz (SSID)", "text",
         "Stesso nome della 2.4 GHz = un'unica rete (consigliato). Nome diverso = due reti separate "
         "con la stessa password; il band steering non serve più.",
         read=_ssid_5g, build=_ssid_5g_set),
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
    Item("wifi_schedule", "rete", "Orari del Wi-Fi", "text",
         "Fascia in cui la rete è accesa, tutti i giorni (es. 07:00-23:00). Fuori orario il Wi-Fi è spento per tutti. "
         "Vuoto = sempre acceso.", read=_schedule, build=_schedule_set),
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
    Item("band_steering", "radio", "Band steering", "choice",
         "Spinge i dispositivi compatibili sulla 5 GHz, più veloce. Standard = suggerisce, forzato = insiste.",
         choices=["disable", "standard", "force"],
         read=lambda c: _ssid_value(c, "bandselect mode"),
         build=lambda v, c: _in_ssid(c, f"bandselect mode {v}")),
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
    Item("min_rate_24", "radio", "Velocità minima 2.4 GHz", "choice",
         "Toglie le velocità più lente (1–5,5 Mbps): i dispositivi vicini occupano meno il canale. "
         "Chi ha segnale molto debole potrebbe non collegarsi più. "
         "Compare dopo Esplora comandi, sugli AP che la hanno.",
         choices=["1", "2", "5.5", "6", "9", "11", "12", "18", "24"], unit="Mbps",
         read=lambda c: _radio_value(c, 1, "2g-wlan-rate-control"),
         build=lambda v, c: _in_radio(c, 1, f"2g-wlan-rate-control {v}")),
    Item("legacy_reject", "radio", "Rifiuta i dispositivi solo 802.11b", "bool",
         "Senza dispositivi 802.11b gli AP non devono più rallentare ogni trasmissione per proteggerli: "
         "il canale 2.4 GHz si libera. Esclude solo apparecchi di prima del 2003.",
         read=lambda c: _radio_flag(c, 1, "reject-legacy-station"),
         build=lambda v, c: _in_radio(c, 1, "reject-legacy-station" if v else "no reject-legacy-station")),
    Item("load_balancing", "radio", "Bilanciamento del carico", "bool",
         "Distribuisce i dispositivi fra le radio quando un AP è troppo affollato.",
         read=_lb, build=_lb_set),
    # --- sistema ---
    Item("led_off", "sistema", "LED spenti", "bool", "Utile per gli AP in camera da letto.",
         read=lambda c: "led_suppress enable" in c.top,
         build=lambda v, c: ["led_suppress enable" if v else "led_suppress disable"]),
    Item("scheduled_reboot", "sistema", "Riavvio programmato", "choice",
         "Riavvia gli AP a un orario fisso, di notte: utile se dopo giorni di funzionamento rallentano.",
         choices=["off", "daily-04", "sun-04", "sat-04"], read=_reboot, build=_reboot_set),
    Item("snmp_rw", "sistema", "SNMP in scrittura", "bool",
         "Consente di modificare l'AP via SNMP con la community: meglio spento, la dashboard legge soltanto.",
         read=_snmp_rw, build=_snmp_rw_off),
    Item("ntp_server", "sistema", "Server dell'ora (NTP)", "text", "Es. time.google.com o l'IP di OPNsense.",
         read=_ntp, build=_ntp_set),
    Item("hostname_sync", "sistema", "Nome dell'AP uguale a quello della dashboard", "bool",
         "Imposta l'hostname di ogni AP con il nome usato qui (es. SOGGIORNO).", per_ap=True,
         read=lambda c: None, build=lambda v, c: []),
]

# voci che si possono personalizzare per un singolo AP (scelte e sì/no; testi e password restano del sito)
PER_AP_KINDS = {"bool", "choice"}
BY_KEY = {i.key: i for i in ITEMS}


def hybrid_mode(cfg: RunningConfig) -> str | None:
    """"cloud" (Nebula) o "standalone" dalla prima riga "hybrid-mode" della running-config."""
    for line in cfg.top:
        if line.startswith("hybrid-mode "):
            return line.split()[1]
    return None


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
    if item.kind == "text" and item.key in ("guest_name", "wifi_schedule") and s == "":
        return s                                   # vuoto = rete ospiti spenta / Wi-Fi sempre acceso
    if item.key == "wifi_schedule":
        if not SCHEDULE_RE.match(s):
            raise ValueError("formato HH:MM-HH:MM, es. 07:00-23:00")
        return s
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
