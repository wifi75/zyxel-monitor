"""Risoluzione nomi: MAC→IP dalla tabella ARP, IP→hostname via DNS inverso (router)."""
import asyncio
import re
import socket
import sys
import time
from pathlib import Path

_dns_cache: dict[str, tuple[float, str | None]] = {}
DNS_TTL = 3600


async def arp_table() -> dict[str, str]:
    """Restituisce {mac: ip}. Su Linux legge /proc/net/arp, su macOS usa `arp -an`."""
    table: dict[str, str] = {}
    proc_arp = Path("/proc/net/arp")
    if proc_arp.exists():
        for line in proc_arp.read_text().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                table[parts[3].lower()] = parts[0]
        return table
    if sys.platform == "darwin":
        proc = await asyncio.create_subprocess_exec(
            "arp", "-an", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await proc.communicate()
        for m in re.finditer(r"\(([\d.]+)\) at ([0-9a-f:]+)", out.decode()):
            mac = ":".join(p.zfill(2) for p in m.group(2).split(":"))
            table[mac] = m.group(1)
    return table


async def hostname(ip: str | None) -> str | None:
    if not ip:
        return None
    now = time.time()
    cached = _dns_cache.get(ip)
    if cached and now - cached[0] < DNS_TTL:
        return cached[1]
    loop = asyncio.get_running_loop()
    try:
        name = (await asyncio.wait_for(loop.run_in_executor(None, socket.gethostbyaddr, ip), 3))[0]
        name = name.split(".")[0]
    except (OSError, TimeoutError):
        name = None
    _dns_cache[ip] = (now, name)
    return name
