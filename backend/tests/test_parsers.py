from app.collectors.ssh import parse_stations
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
