from app.collectors.ssh import (
    parse_channels, parse_hal_radios, parse_hal_statistic, parse_port_status, parse_stations, parse_traffic, parse_version,
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
