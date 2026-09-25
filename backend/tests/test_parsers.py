from app.collectors.ssh import (
    parse_channels, parse_cpu_mem, parse_hal_radios, parse_hal_statistic, parse_port_status, parse_stations, parse_traffic, parse_version,
)
from app.devices import device_type
from app.poller import site_of

SAMPLE = """Router> show wireless-hal station info
index: 0
  MAC: 7a:66:9a:20:49:64
  IPv4: 192.168.1.221
  SSID: WiFi
  TxRate: 172M
  RxRate: 154M
  RSSI dBm: -62
  Time: 2026/09/23 16:40:29
  Capability: 802.11ax
  Band: 2.4GHz
index: 0
  MAC: 06:08:78:97:87:B5
  IPv4: 192.168.1.211
  RSSI dBm: -68
  Band: 5GHz
Router> exit
"""


def test_parse_stations():
    clients = parse_stations(SAMPLE)
    assert [c.mac for c in clients] == ["7a:66:9a:20:49:64", "06:08:78:97:87:b5"]
    first = clients[0]
    assert (first.ip, first.band, first.rssi_dbm, first.tx_rate, first.rx_rate) == (
        "192.168.1.221", "2.4GHz", -62, 172, 154)
    assert first.connected_at is not None
    assert clients[1].band == "5GHz"


def test_site_of():
    assert site_of("www.facebook.com.", "") == "facebook.com"
    assert site_of("news.bbc.co.uk.", "") == "bbc.co.uk"
    assert site_of("1.1.168.192.in-addr.arpa.", "") is None
    assert site_of("nas.casa.lan.", "") is None
    assert site_of("maxpoll.example.eu.", "example.eu") is None
    assert site_of("localhost.", "") is None


def test_device_type():
    assert device_type("shelly-luci-giardino", "98:f4:ab:f3:d8:7b") == "Domotica"
    assert device_type("iphone", "7a:66:9a:20:49:64") == "Smartphone"
    assert device_type("inverter-deye", "e8:fd:f8:fe:66:ce") == "Energia"
    assert device_type(None, "7a:66:9a:20:49:64") == "Smartphone"   # MAC privato
    assert device_type(None, "e8:fd:f8:fe:66:ce") == "Altro"


def test_parse_version_uptime():
    assert parse_version("system uptime: 1 day(s), 02:03:04")[2] == 86400 + 2 * 3600 + 3 * 60 + 4
    assert parse_version("system uptime: 05:00:10")[2] == 5 * 3600 + 10


def test_parse_traffic():
    zld = "Name: wlan-1-1\n  Rx bytes: 1000\n  Tx bytes: 2000\nName: eth0\n  RX Octets: 5\n  TX Octets: 6\n"
    assert parse_traffic(zld) == {"wlan-1-1": (1000, 2000), "eth0": (5, 6)}
    ifconfig = "wlan-2-1  Link encap:Ethernet\n          RX bytes:30 (30.0 B)  TX bytes:40 (40.0 B)\n"
    assert parse_traffic(ifconfig) == {"wlan-2-1": (30, 40)}


def test_parse_traffic_detail_echo():
    text = (
        "Router> show interface wlan-1-1\n  RX bytes: 11\n  TX bytes: 22\n"
        "Router> show interface wlan-2-1\n  RX bytes: 3\n  TX bytes: 4\n"
    )
    assert parse_traffic(text) == {"wlan-1-1": (11, 22), "wlan-2-1": (3, 4)}
    assert parse_version("system uptime: 1 days 14:09:23")[2] == 86400 + 14 * 3600 + 9 * 60 + 23


HAL = """Router> show wireless-hal statistic
Slot: 1
  ReceivedPktCount: 30882186
  TransmittedPktCount: 18826673
  wlanReceivedByte: 22887452952
  wlanTransmittedByte: 2483682712
  RetryCount: 0
  Channel Utilization: 10
Slot: 2
  ReceivedPktCount: 3335106
  wlanReceivedByte: 554871106
  wlanTransmittedByte: 1672752884
Router> show port status
Port Status       TxPkts     RxPkts     TxBcast    RxBcast    Colli.  TxB/s      RxB/s      Up Time      PVID       TxBytes              RxBytes
=================================================================================================
1    2500M/Full   25486082   17272144   0          0          0       115314     12806      38:19:30     1          21918515539          2851259939
Router> exit
"""


def test_parse_hal_statistic_and_port():
    assert parse_hal_statistic(HAL) == {"wlan-1-1": (22887452952, 2483682712), "wlan-2-1": (554871106, 1672752884)}
    assert parse_port_status(HAL) == {"eth0": (2851259939, 21918515539)}


def test_parse_hal_radios():
    text = "Slot: 1\n  TxPower: 20\n  Channel Utilization: 10\nSlot: 2\n  TxPower: 21\n  Channel Utilization: 1\n"
    assert parse_hal_radios(text) == {
        "2.4GHz": {"tx_power": 20, "utilization": 10},
        "5GHz": {"tx_power": 21, "utilization": 1},
    }


def test_parse_channels():
    text = "Router> show wireless-hal current\nSlot: 1\n  Channel: 6\nSlot: 2\n  Channel: 44\nRouter> show port status\nChannel: 99\n"
    assert parse_channels(text) == {"2.4GHz": 6, "5GHz": 44}


def test_parse_cpu_mem():
    text = (
        "Router> show cpu status\nCPU utilization: 4 %\nCPU utilization for 1 min: 3 %\n"
        "Router> show mem status\nmemory usage: 50%\n"
    )
    assert parse_cpu_mem(text) == (4, 50)


def test_radio_profiles_and_commands():
    from app.collectors.ssh import radio_commands, slot_profiles
    cfg = "wlan slot1\n ap profile RADIO_SETTING_TYPE_2\n output-power 20dBm\n!\nwlan slot2\n ap profile RADIO_SETTING_TYPE_5\n!\n"
    assert slot_profiles(cfg) == {1: "RADIO_SETTING_TYPE_2", 2: "RADIO_SETTING_TYPE_5"}
    assert radio_commands("2.4GHz", "P", "auto", None) == ["wlan-radio-profile P", "dcs activate", "exit"]
    assert radio_commands("5GHz", "P", "100", "20/40/80") == [
        "wlan-radio-profile P", "no dcs activate", "5g-channel 100", "ch-width 20/40/80", "exit",
    ]


def test_config_items_read_and_build():
    from app import config_items as ci
    text = (
        "hostname SOGGIORNO\n!\nwlan-security-profile SECURITY1\n mode wpa2\n dot11r activate\n!\n"
        "wlan-ssid-profile SSID1\n ssid WiFi\n security SECURITY1\n downlink-rate-limit 0 kbps\n dot11k-v activate\n!\n"
        "wlan-radio-profile RADIO_SETTING_TYPE_2\n rssi-thres\n rssi-kickout -70\n!\n"
        "wlan slot1\n ap profile RADIO_SETTING_TYPE_2\n ssid profile 1 SSID1\n!\n"
        "snmp-server community ZyxelAP ro\nsnmp-server community ZyxelAP rw\n!\nntp server time.google.com\n!\n"
        "led_suppress disable\n"
    )
    cfg = ci.RunningConfig(text)
    v = {i.key: i.read(cfg) for i in ci.ITEMS}
    assert v["ssid_name"] == "WiFi" and v["rate_down"] == 0 and v["dot11kv"] and v["dot11r"]
    assert v["rssi_kickout"] == -70 and v["snmp_rw"] and v["ntp_server"] == "time.google.com" and not v["led_off"]
    assert ci.BY_KEY["ssid_name"].build("Casa", cfg) == ["wlan-ssid-profile SSID1", "ssid Casa", "exit"]
    assert ci.BY_KEY["snmp_rw"].build(False, cfg) == ["no snmp-server community ZyxelAP rw"]
    assert ci.hostname_commands("ZONA NOTTE", cfg) == ["hostname ZONA-NOTTE"]


def test_parse_stations_old_firmware():
    text = (
        "Router> show wireless-hal station info\nindex: 0\n  MAC: 08:f9:e0:71:fc:15\n  IPv4: 192.168.1.141\n"
        "  Slot: 1\n  RSSI dBm: -69\n  Time: 12:50:36 2026/09/24\n  DOT11 features: 11k\n\n  Display SSID: WiFi\n"
        "Router> exit\n"
    )
    c = parse_stations(text)[0]
    assert c.band == "2.4GHz" and c.connected_at is not None and c.ssid == "WiFi" and c.rssi_dbm == -69


def test_password_hide_macblock():
    from app import config_items as ci
    text = (
        "wlan-security-profile SECURITY1\n mode wpa2\n encrypted-wpa-psk ABC=\n!\n"
        "wlan-macfilter-profile BLOCKED1\n filter-action deny\n aa:bb:cc:dd:ee:ff\n!\n"
        "wlan-ssid-profile SSID1\n ssid WiFi\n security SECURITY1\n macfilter BLOCKED1\n!\n"
        "wlan slot1\n ap profile R2\n ssid profile 1 SSID1\n!\n"
    )
    cfg = ci.RunningConfig(text)
    assert ci.BY_KEY["ssid_hidden"].read(cfg) is False
    assert ci.BY_KEY["mac_block"].read(cfg) == ["aa:bb:cc:dd:ee:ff"]
    assert ci.BY_KEY["mac_block"].build(["11:22:33:44:55:66"], cfg) == [
        "wlan-macfilter-profile BLOCKED1", "filter-action deny", "11:22:33:44:55:66", "no aa:bb:cc:dd:ee:ff", "exit"]
    assert ci.BY_KEY["wifi_password"].build("segreta123", cfg) == [
        "wlan-security-profile SECURITY1", "wpa-psk segreta123", "exit"]
    assert ci.parse_value(ci.BY_KEY["mac_block"], "AA-BB-CC-DD-EE-FF, 11:22:33:44:55:66") == [
        "11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"]


def test_parse_channels_show_wlan():
    text = "Router> show wlan all\nslot1:\n  Channel: 6\nslot2:\n  channel 44\nRouter> exit\n"
    assert parse_channels(text) == {"2.4GHz": 6, "5GHz": 44}


def test_parse_config_channels():
    from app.collectors.ssh import parse_config_channels
    text = (
        "Router> show running-config\n!\nwlan-radio-profile R2\n 2g-channel 6\n dcs activate\n!\n"
        "wlan-radio-profile R5\n 5g-channel 116\n!\nwlan slot1\n ap profile R2\n!\nwlan slot2\n ap profile R5\n!\n"
        "Router> exit\n"
    )
    assert parse_config_channels(text) == {"2.4GHz": (None, True), "5GHz": (116, False)}


def test_security_and_guest():
    from app import config_items as ci
    text = (
        "wlan-security-profile SECURITY1\n mode wpa3\n transition-mode\n!\n"
        "wlan-ssid-profile SSID1\n ssid WiFi\n security SECURITY1\n!\n"
        "wlan-ssid-profile SSID2\n ssid Ospiti\n!\n"
        "wlan slot1\n ap profile R2\n ssid profile 1 SSID1\n!\nwlan slot2\n ap profile R5\n ssid profile 1 SSID1\n!\n"
    )
    cfg = ci.RunningConfig(text)
    assert ci.BY_KEY["security_mode"].read(cfg) == "wpa2/wpa3"
    assert ci.BY_KEY["security_mode"].build("wpa2", cfg) == ["wlan-security-profile SECURITY1", "mode wpa2", "exit"]
    assert ci.BY_KEY["guest_name"].read(cfg) == ""          # SSID2 non è sugli slot: rete ospiti spenta
    off = ci.BY_KEY["guest_name"].build("", cfg)
    assert off == ["wlan slot1", "no ssid profile 2", "exit", "wlan slot2", "no ssid profile 2", "exit"]


def test_band_steering():
    from app import config_items as ci
    cfg = ci.RunningConfig("wlan-ssid-profile SSID1\n ssid WiFi\n bandselect mode disable\n!\nwlan slot1\n ssid profile 1 SSID1\n!\n")
    assert ci.BY_KEY["band_steering"].read(cfg) == "disable"
    assert ci.BY_KEY["band_steering"].build("standard", cfg) == ["wlan-ssid-profile SSID1", "bandselect mode standard", "exit"]


def test_scheduled_reboot():
    from app import config_items as ci
    cfg = ci.RunningConfig("schedule-reboot\n activate\n sun\n reboot-time 04:00\n!\n")
    assert ci.BY_KEY["scheduled_reboot"].read(cfg) == "sun-04"
    assert ci.BY_KEY["scheduled_reboot"].read(ci.RunningConfig("hostname X\n")) == "off"
    cmds = ci.BY_KEY["scheduled_reboot"].build("daily-04", cfg)
    assert cmds[0] == "schedule-reboot" and "mon" in cmds and "reboot-time 04:00" in cmds and cmds[-2:] == ["activate", "exit"]
    assert ci.hybrid_mode(ci.RunningConfig("hybrid-mode cloud\n!\n")) == "cloud"


def test_wifi_schedule():
    from app import config_items as ci
    cfg = ci.RunningConfig("wlan-ssid-profile SSID1\n ssid WiFi\n ssid-schedule\n mon enable 07:00 23:00\n!\nwlan slot1\n ssid profile 1 SSID1\n!\n")
    assert ci.BY_KEY["wifi_schedule"].read(cfg) == "07:00-23:00"
    cmds = ci.BY_KEY["wifi_schedule"].build("08:00-22:30", cfg)
    assert cmds[:2] == ["wlan-ssid-profile SSID1", "ssid-schedule"] and "sun enable 08:00 22:30" in cmds
    assert ci.BY_KEY["wifi_schedule"].build("", cfg) == ["wlan-ssid-profile SSID1", "no ssid-schedule", "exit"]
    assert ci.parse_value(ci.BY_KEY["wifi_schedule"], "07:00-23:00") == "07:00-23:00"


def test_restore_commands():
    from app import config_items as ci
    from app.restore import restore_commands
    old = ci.RunningConfig("wlan-security-profile S1\n mode wpa2\n!\nwlan slot1\n output-power 16dBm\n ssid profile 1 SSID1\n!\n")
    now = ci.RunningConfig("wlan-security-profile S1\n mode wpa3\n transition-mode\n!\n"
                           "wlan slot1\n output-power 19dBm\n ssid profile 1 SSID1\n!\n")
    assert restore_commands(old, now) == ["wlan-security-profile S1", "no transition-mode", "mode wpa2", "exit",
                                          "wlan slot1", "output-power 16dBm", "exit"]


def test_guard_mask_password():
    from app.guard import _mask
    assert _mask(["wlan-security-profile S1", "wpa-psk segreta123", "exit"]) == [
        "wlan-security-profile S1", "wpa-psk ••••••••", "exit"]


def test_capabilities():
    from app import capabilities as cap
    assert cap.generation("NWA50AX PRO") == 6 and cap.generation("WAC6103D-I") == 5
    wifi5 = cap.of_model("NWA1123-AC PRO")
    assert cap.fit_width("20/40/80/160", "5GHz", wifi5) == "20/40/80"
    assert cap.fit_width("20/40/80/160", "5GHz", cap.of_model("NWA50AX PRO")) == "20/40/80/160"


def test_capabilities_items():
    from app import capabilities as cap
    wifi5, wifi6 = cap.of_model("WAC6103D-I"), cap.of_model("NWA50AX PRO")
    assert cap.fit_item("security_mode", "wpa2/wpa3", wifi5) == "wpa2"
    assert cap.fit_item("security_mode", "wpa2/wpa3", wifi6) == "wpa2/wpa3"
    assert not cap.available("dot11r", None, "bool") and cap.available("wifi_password", None, "password")
