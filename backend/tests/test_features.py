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


def test_widths_from_cli_help():
    from app.capabilities import parse_widths
    garage = "Router(config-wlan-radio R2)# ch-width \n20m                     \n<20, 20/40, 20/40/80>   \nauto\n"
    assert parse_widths(garage) == ["20", "20/40", "20/40/80"]
    assert parse_widths("nessun aiuto") == []


def test_ap_override_wins_over_site(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "o.db"))
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app import site_config
    from app.core.db import init_db
    init_db()
    site_config.set_value("min_rate_24", "1")
    site_config.set_override(3, "min_rate_24", "12")
    site_config.set_override(4, "min_rate_24", site_config.UNMANAGED)
    assert site_config.for_ap(3)["min_rate_24"] == "12"
    assert "min_rate_24" not in site_config.for_ap(4)
    assert site_config.for_ap(5)["min_rate_24"] == "1"
    assert "min_rate_24@ap:3" not in site_config.load()
    get_settings.cache_clear()


def test_legacy_reject_read_and_commands():
    from app.config_items import BY_KEY, RunningConfig
    cfg = RunningConfig("wlan slot1\n ap profile R2\n!\nwlan-radio-profile R2\n reject-legacy-station\n!\n")
    item = BY_KEY["legacy_reject"]
    assert item.read(cfg) is True
    assert item.build(False, cfg) == ["wlan-radio-profile R2", "no reject-legacy-station", "exit"]


def test_critical_device_alert_after_five_minutes_and_on_return():
    from app.alerts import critical_changes
    rows = [{"mac": "aa", "name": "inverter", "last_seen": 1000, "ap": "GARAGE"}]
    lines, still = critical_changes(rows, online=set(), alerted=set(), now=1200)
    assert not lines and not still                       # solo 200 s: si aspetta
    lines, still = critical_changes(rows, online=set(), alerted=set(), now=1400)
    assert "scollegato" in lines[0] and still == {"aa"}
    lines, still = critical_changes(rows, online=set(), alerted=still, now=2000)
    assert not lines                                     # già avvisato: niente ripetizioni
    lines, still = critical_changes(rows, online={"aa"}, alerted=still, now=2100)
    assert "di nuovo collegato" in lines[0] and not still


def test_type_from_vendor_when_name_says_nothing(monkeypatch):
    from app import oui
    from app.devices import device_type
    monkeypatch.setattr(oui, "vendor", lambda mac: "Espressif")
    assert device_type("lwip0", "24:62:ab:d7:1b:bc") == "Microcontrollori"
    assert device_type("shelly-cancello", "24:62:ab:d7:1b:bc") == "Domotica"   # il nome vale di più


def test_wifi_generation_from_model():
    from app.capabilities import generation, of_model
    assert generation("NWA50AX PRO") == 6
    assert generation("WAC6103D-I") == 5
    assert generation("NWA50BE PRO") == 7 and generation("WBE660S") == 7
    assert "20/40/80/160" in of_model("WBE660S")["widths"]["5GHz"]


def test_radio_sends_only_what_changes():
    from app.config_items import RunningConfig
    from app.policy import radio_diff, radio_now
    cfg = RunningConfig("wlan slot1\n ap profile R2\n output-power 30dBm\n!\nwlan slot2\n ap profile R5\n output-power 30dBm\n!\n"
                        "wlan-radio-profile R2\n 2g-channel 11\n ch-width 20\n!\nwlan-radio-profile R5\n dcs activate\n"
                        " ch-width 20/40/80\n!\n")
    same = {"tx_power": 30, "channel": "11", "width": "20"}
    assert radio_diff(same, radio_now(cfg, "2.4GHz")) == {}
    # solo la larghezza del 5 GHz cambia: niente potenza né canale
    assert radio_diff({"tx_power": 30, "channel": "auto", "width": "20/40/80/160"}, radio_now(cfg, "5GHz")) == \
        {"width": "20/40/80/160"}
    assert radio_diff({"tx_power": 30, "channel": "auto", "width": "80"}, radio_now(cfg, "5GHz")) == {}


def test_only_system_settings_skip_the_trial():
    from app.guard import is_quick
    assert is_quick({"led_off"}, radio=False)
    assert not is_quick({"led_off", "wifi_password"}, radio=False)
    assert not is_quick({"led_off"}, radio=True)
    assert not is_quick(None, radio=False)


def test_text_choices_compare_as_text():
    from app.config_items import BY_KEY, same
    assert same(BY_KEY["security_mode"], "wpa2", "wpa2")
    assert same(BY_KEY["band_steering"], "standard", "standard")
    assert not same(BY_KEY["band_steering"], "standard", "disable")
    assert same(BY_KEY["rssi_kickout"], "-70", "-70")


def test_realignment_stops_after_repeated_reapply(monkeypatch):
    from app import site_config
    monkeypatch.setattr(site_config, "_event", lambda ap, info: None)
    site_config._reapplied.clear()
    site_config.stuck.clear()
    assert not site_config._conflict("ZN", "band_steering", "Band steering", False)
    assert not site_config._conflict("ZN", "band_steering", "Band steering", False)
    assert site_config._conflict("ZN", "band_steering", "Band steering", False)     # terza volta: basta
    assert ("ZN", "band_steering") in site_config.stuck


def test_diagnosis_blames_kickout_when_drops_happen_near_threshold():
    from app.diagnosis import analyse
    ev, t = [], 1000
    for i in range(8):
        ev += [{"id": 2 * i, "ts": t, "kind": "connect", "ap": "ZN", "info": "5GHz"},
               {"id": 2 * i + 1, "ts": t + 120, "kind": "disconnect", "ap": "ZN", "info": None}]
        t += 200
    r = analyse(ev, lambda ts: -71, {}, {}, kickout=-70, siblings=0, hours=24)
    titles = [f["title"] for f in r["findings"]]
    assert r["stats"]["drops"] == 8 and r["stats"]["short_sessions"] == 8
    assert "Staccato dall'AP per segnale debole" in titles


def test_diagnosis_blames_reconfiguration():
    from app.diagnosis import analyse
    ev = [{"id": 1, "ts": 1000, "kind": "connect", "ap": "ZN", "info": "5GHz"},
          {"id": 2, "ts": 2000, "kind": "disconnect", "ap": "ZN", "info": None}]
    r = analyse(ev, lambda ts: -55, {"ZN": [1950]}, {}, kickout=-70, siblings=0, hours=24)
    assert any(f["title"] == "Staccato da una riconfigurazione dell'AP" for f in r["findings"])


def test_download_and_upload_from_insight_rows():
    from app.collectors.opnsense import split_traffic
    rows = [
        # interfaccia di casa (tanti ingressi da indirizzi privati)
        {"if": "vtnet0", "direction": "in", "src_addr": "192.168.1.211", "dst_addr": "1.2.3.4", "octets": "400"},
        {"if": "vtnet0", "direction": "out", "src_addr": "192.168.1.211", "dst_addr": "1.2.3.4", "octets": "3300"},
        {"if": "vtnet0", "direction": "in", "src_addr": "192.168.1.50", "dst_addr": "1.2.3.4", "octets": "10"},
        # stessa cosa vista dalla WAN: non va contata una seconda volta
        {"if": "vlan0.2", "direction": "in", "src_addr": "1.2.3.4", "dst_addr": "192.168.1.211", "octets": "3300"},
    ]
    out = split_traffic(rows)
    assert out["192.168.1.211"] == [3300, 400]


def test_vlan_read_and_command():
    from app.config_items import BY_KEY, RunningConfig
    cfg = RunningConfig("wlan slot1\n ssid profile 1 SSID1\n!\nwlan-ssid-profile SSID1\n ssid WiFi\n vlan-id 1\n!\n")
    assert BY_KEY["vlan_id"].read(cfg) == 1
    assert BY_KEY["vlan_id"].build(20, cfg) == ["wlan-ssid-profile SSID1", "vlan-id 20", "exit"]
