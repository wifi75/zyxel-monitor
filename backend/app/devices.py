"""Classificazione del tipo di dispositivo a partire da nome host / alias / MAC."""
import re

# (tipologia, pattern sul nome) — il primo che corrisponde vince
RULES: list[tuple[str, str]] = [
    ("Smartphone", r"iphone|android|galaxy|pixel|redmi|xiaomi|oneplus|huawei|oppo|motorola|phone"),
    ("Tablet", r"ipad|tab|tablet|kindle"),
    ("Computer", r"macbook|imac|mac-|mbp|laptop|notebook|desktop|pc|windows|thinkpad|surface"),
    ("TV e media", r"tv|chromecast|firetv|fire-tv|roku|appletv|apple-tv|sonos|echo|alexa|nest|homepod"),
    ("Domotica", r"shelly|tasmota|sonoff|tuya|hue|meross|tapo|plug|presa|luce|luci|switch|tapparella"
                 r"|clima|condizionatore|hisense|daikin"),
    ("Microcontrollori", r"esp|esp32|esp8266|arduino|wemos"),
    ("Energia", r"inverter|deye|bms|fronius|solar|victron|meter"),
    ("Stampanti", r"print|stampante|epson|canon|brother|hp-"),
    ("Telecamere", r"cam|camera|ipcam|reolink|hikvision|dahua|ezviz"),
    ("Console", r"playstation|ps4|ps5|xbox|switch-nintendo|nintendo"),
]
_COMPILED = [(t, re.compile(p, re.I)) for t, p in RULES]


def is_private_mac(mac: str) -> bool:
    try:
        return bool(int(mac[:2], 16) & 0x02)
    except ValueError:
        return False


def device_type(name: str | None, mac: str) -> str:
    if name:
        for kind, rx in _COMPILED:
            if rx.search(name):
                return kind
    # iOS e Android recenti usano MAC privati: quasi sempre smartphone/tablet
    if is_private_mac(mac):
        return "Smartphone"
    return "Altro"
