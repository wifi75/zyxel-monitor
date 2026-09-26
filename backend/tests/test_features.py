import csv

from app import oui
from app.channels import analyse
from app.devices import is_private_mac


def test_private_mac_detected():
    assert is_private_mac("da:a1:19:00:00:01")
    assert oui.vendor("da:a1:19:00:00:01") == oui.PRIVATE


def test_vendor_from_csv(tmp_path, monkeypatch):
    f = tmp_path / "oui.csv"
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Registry", "Assignment", "Organization Name", "Organization Address"])
        w.writerow(["MA-L", "F0189B", "Apple, Inc.", "Cupertino"])
    monkeypatch.setattr(oui, "_CANDIDATES", (str(f),))
    oui.table.cache_clear()
    assert oui.vendor("F0:18:9B:12:34:56") == "Apple"
    assert oui.vendor("00:11:22:33:44:55") is None
    oui.table.cache_clear()


def _ap(name, ch24, ch5, util=None):
    return {"ap": name, "online": True, "radios": [
        {"band": "2.4GHz", "channel": ch24, "clients": 1, "utilization": util},
        {"band": "5GHz", "channel": ch5, "clients": 1, "utilization": None},
    ]}


def test_channels_overlap_and_suggestion():
    r = analyse([_ap("A", 1, 36), _ap("B", 1, 36), _ap("C", 3, 44)])
    b24 = r["bands"]["2.4GHz"]
    assert {i["kind"] for i in b24["issues"]} >= {"same", "overlap"}
    # tre AP in 2.4: il suggerimento usa 1, 6, 11 senza ripetizioni
    assert sorted(b24["suggested"].values()) == [1, 6, 11]
    # A e B sullo stesso canale: un solo avviso con entrambi
    assert [i["aps"] for i in b24["issues"] if i["kind"] == "same"] == [["A", "B"]]
    assert len(set(r["bands"]["5GHz"]["suggested"].values())) == 3


def test_channels_clean_plan_has_no_issues():
    r = analyse([_ap("A", 1, 36), _ap("B", 6, 52), _ap("C", 11, 100)])
    assert not r["bands"]["2.4GHz"]["issues"]
    assert not r["bands"]["5GHz"]["issues"]


def test_short_ap_blip_is_not_alerted():
    from app.alerts import pending_events
    rows = [
        {"id": 1, "ts": 1000, "kind": "ap_down", "ap": "GARAGE"},
        {"id": 2, "ts": 1060, "kind": "ap_up", "ap": "GARAGE"},
        {"id": 3, "ts": 1100, "kind": "wan_down", "ap": None},
        {"id": 4, "ts": 1990, "kind": "new_device", "ap": "SOGGIORNO"},   # troppo recente: al giro dopo
    ]
    events, last = pending_events(rows, now=2000, grace=105)
    assert [e["id"] for e in events] == [3]
    assert last == 3


def test_long_ap_outage_is_alerted():
    from app.alerts import pending_events
    rows = [{"id": 1, "ts": 1000, "kind": "ap_down", "ap": "GARAGE"},
            {"id": 2, "ts": 1600, "kind": "ap_up", "ap": "GARAGE"}]
    events, _ = pending_events(rows, now=2000, grace=105)
    assert [e["kind"] for e in events] == ["ap_down", "ap_up"]


def test_login_locks_after_repeated_failures(monkeypatch):
    from app import api
    monkeypatch.setattr(api, "_fails", {"admin": [api.time.time()] * api.MAX_FAILS})
    assert api._locked("admin") > 0
    assert api._locked("altro") == 0


def test_air_conditioner_with_private_mac_is_home_automation():
    from app.devices import device_type
    assert device_type("hisense-clima-studio", "ca:2c:4f:5e:e0:31") == "Domotica"


def test_min_rate_offered_only_to_aps_that_declare_it(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app import capabilities
    from app.core.db import init_db
    init_db()
    help_text = "2g-wlan-rate-control \n<2.4G Minimum rate control 1,2,5.5,6,9,11,12,18,24,36,48,54>"
    assert capabilities.learn("GARAGE", help_text) == ["min_rate_24"]
    assert capabilities.available("min_rate_24", None, "choice", "GARAGE")
    assert not capabilities.available("min_rate_24", None, "choice", "GIARDINO")
    assert capabilities.current("min_rate_24", None, "GARAGE") == "1"
    get_settings.cache_clear()


def test_explore_never_asks_about_valueless_commands():
    from app.config_items import RunningConfig
    from app.site_config import explore_commands
    cfg = RunningConfig("wlan slot1\n ap profile R2\n!\nwlan slot2\n ap profile R5\n!\n")
    assert not any(line.startswith("reject-legacy-station") for line in explore_commands(cfg))
