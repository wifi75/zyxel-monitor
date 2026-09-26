"""Screenshot per il README, dal pannello in modalità dimostrativa (scripts/demo_data.py + ZM_DEMO=1).

Serve Playwright (pip install playwright) e usa Edge già installato:

    python scripts/screenshots.py http://127.0.0.1:8010
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
USER, PASSWORD, NEW_PASSWORD = "admin", "Admin12345", "DemoScreens2026"


def _post(path: str, body: dict, tok: str | None = None) -> dict:
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def token() -> str:
    """Accesso al database dimostrativo; la prima volta si cambia la password predefinita (sparisce il banner)."""
    try:
        tok = _post("/api/login", {"username": USER, "password": PASSWORD})["token"]
        _post("/api/password", {"old_password": PASSWORD, "new_password": NEW_PASSWORD}, tok)
    except urllib.error.HTTPError:
        pass
    return _post("/api/login", {"username": USER, "password": NEW_PASSWORD})["token"]


def shot(page: Page, name: str, wait: str, full: bool = False, nav: str | None = None, sub: str | None = None) -> None:
    if nav:
        page.locator(".nav-item", has_text=nav).first.click()
    if sub:
        page.locator(".nav-item.sub", has_text=sub).click()
    page.wait_for_selector(wait)
    page.wait_for_timeout(2000)          # grafici disegnati
    page.screenshot(path=OUT / f"{name}.png", full_page=full)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tok = token()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        for theme in ("light", "dark"):
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.add_init_script(f"localStorage.setItem('zm_token', {json.dumps(tok)});"
                                 f"localStorage.setItem('zm_lang', 'en'); localStorage.setItem('zm-theme', '{theme}');")
            page.goto(BASE)
            shot(page, f"overview-{theme}", ".kpis", full=theme == "light")
            if theme == "light":
                shot(page, "access-point", ".ap-hero", sub="Garage")
                shot(page, "devices", "table", nav="Devices")
                shot(page, "report", ".kpis", full=True, nav="Report")
                shot(page, "settings", ".settings-page", nav="Settings")
            page.close()
        browser.close()
    print("screenshot salvati in", OUT)


if __name__ == "__main__":
    main()
