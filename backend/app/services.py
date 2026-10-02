"""Traffico per servizio (YouTube, Netflix, WhatsApp…) senza DPI: dagli indirizzi remoti di NetFlow.

Nebula Pro riconosce le applicazioni ispezionando i pacchetti; qui si guarda solo *con chi* parla la casa.
Ogni indirizzo remoto si traduce col DNS inverso ("fra16s52-in-f14.1e100.net") e il nome si riconduce a un
servizio con una tabella di suffissi noti. È una stima: il traffico verso una CDN condivisa (Akamai,
Cloudflare) resta sotto il nome della CDN, perché dall'indirizzo non si vede quale sito serviva.
"""
import asyncio
import ipaddress
import socket
import time

# suffisso del nome inverso (o parte del nome) → servizio. Il primo che corrisponde vince.
SERVICES: list[tuple[str, str]] = [
    ("nflxvideo.net", "Netflix"), ("nflximg", "Netflix"), ("netflix", "Netflix"),
    ("googlevideo.com", "YouTube"), ("youtube", "YouTube"), ("ytimg", "YouTube"),
    ("1e100.net", "Google"), ("google", "Google"), ("gvt1.com", "Google"),
    ("whatsapp", "WhatsApp"), ("fbcdn.net", "Facebook / Instagram"), ("facebook", "Facebook / Instagram"),
    ("instagram", "Facebook / Instagram"), ("cdninstagram", "Facebook / Instagram"),
    ("tiktok", "TikTok"), ("bytedance", "TikTok"), ("ttlivecdn", "TikTok"),
    ("aaplimg.com", "Apple"), ("apple.com", "Apple"), ("icloud", "Apple"),
    ("msedge.net", "Microsoft"), ("microsoft", "Microsoft"), ("windowsupdate", "Microsoft"),
    ("azure", "Microsoft"), ("live.com", "Microsoft"), ("office", "Microsoft"), ("teams", "Microsoft"),
    ("amazonvideo", "Prime Video"), ("aiv-cdn", "Prime Video"), ("amazonaws.com", "Amazon AWS"),
    ("amazon", "Amazon"), ("alexa", "Amazon"), ("cloudfront.net", "Amazon CloudFront"),
    ("spotify", "Spotify"), ("scdn.co", "Spotify"), ("dazn", "DAZN"), ("disney", "Disney+"),
    ("dssott", "Disney+"), ("twitch", "Twitch"), ("steam", "Steam"), ("valve", "Steam"),
    ("playstation", "PlayStation"), ("sony", "PlayStation"), ("xbox", "Xbox"), ("nintendo", "Nintendo"),
    ("zoom.us", "Zoom"), ("telegram", "Telegram"), ("tuya", "Tuya (casa smart)"),
    ("akamai", "Akamai (CDN)"), ("cloudflare", "Cloudflare (CDN)"), ("fastly", "Fastly (CDN)"),
    ("edgecast", "Edgecast (CDN)"), ("zyxel", "Zyxel / Nebula"),
]
TTL = 6 * 3600
_cache: dict[str, tuple[float, str | None]] = {}


def service_of(name: str | None) -> str | None:
    if not name:
        return None
    low = name.lower()
    for sign, service in SERVICES:
        if sign in low:
            return service
    return None


def registered(name: str) -> str:
    """"host.esempio.co.uk" → "esempio.co.uk", "a.b.esempio.it" → "esempio.it" (abbastanza per un'etichetta)."""
    parts = name.lower().rstrip(".").split(".")
    if len(parts) >= 3 and len(parts[-2]) <= 3 and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


async def reverse(ip: str) -> str | None:
    now = time.time()
    hit = _cache.get(ip)
    if hit and now - hit[0] < TTL:
        return hit[1]
    loop = asyncio.get_running_loop()
    try:
        name = (await asyncio.wait_for(loop.run_in_executor(None, socket.gethostbyaddr, ip), 3))[0]
    except (OSError, TimeoutError):
        name = None
    _cache[ip] = (now, name)
    return name


def is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_global and not a.is_multicast


async def group(per_remote: dict[str, int], top: int = 60) -> list[dict]:
    """{ip remoto: byte} → [{name, bytes}] per servizio. Si risolvono solo i `top` indirizzi più pesanti:
    il resto finisce in "Altro" (di solito è una coda lunga di pochi kB)."""
    heavy = sorted(per_remote.items(), key=lambda kv: kv[1], reverse=True)
    resolve, rest = heavy[:top], heavy[top:]
    names = await asyncio.gather(*(reverse(ip) for ip, _ in resolve))
    totals: dict[str, int] = {}
    for (_ip, n), name in zip(resolve, names, strict=True):
        label = service_of(name) or (registered(name) if name else "Senza nome")
        totals[label] = totals.get(label, 0) + n
    other = sum(n for _, n in rest)
    if other:
        totals["Altro"] = totals.get("Altro", 0) + other
    return [{"name": k, "bytes": v} for k, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)]
