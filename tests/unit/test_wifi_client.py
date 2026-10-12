"""A Wi-Fi inbound adapter joining a network as a client: wpa_supplicant's settings, joining,
the address by DHCP and leaving. No root, no radio: commands go to a recording runner."""

import os
import stat

import pytest

from wanpire.engine import CommandFailed
from wanpire.wifi_client import WifiClient, WifiClientFailed, wpa_settings

NET = {"ssid": "upstream", "passphrase": "correct horse"}


def lines(text):
    return [line.strip() for line in text.splitlines() if line.strip() and
            not line.strip().startswith("#")]


def test_the_settings_for_wpa2_and_wpa3_personal():
    text = lines(wpa_settings("wlan1", NET, "/run/wanpire/wpa-wlan1", "GB"))
    for want in ("ctrl_interface=/run/wanpire/wpa-wlan1", "country=GB", "network={",
                 f"ssid={'upstream'.encode().hex()}", "scan_ssid=0",
                 "key_mgmt=WPA-PSK WPA-PSK-SHA256 SAE", "ieee80211w=1",
                 'psk="correct horse"', 'sae_password="correct horse"', "}"):
        assert want in text, want


def test_an_open_network():
    text = lines(wpa_settings("wlan1", {"ssid": "cafe", "passphrase": ""}, "/s", None))
    assert "key_mgmt=NONE" in text
    assert not [line for line in text if line.startswith(("psk", "sae_password", "country"))]


def test_a_64_digit_key_is_written_as_is_and_without_wpa3():
    key = "ab" * 32
    text = lines(wpa_settings("wlan1", {"ssid": "up", "passphrase": key}, "/s", "GB"))
    assert f"psk={key}" in text and "key_mgmt=WPA-PSK WPA-PSK-SHA256" in text
    assert not [line for line in text if line.startswith("sae_password")]


def test_a_name_that_is_not_plain_text_is_written_in_hexadecimal():
    ssid = 'up"stream\n}'
    text = lines(wpa_settings("wlan1", {"ssid": ssid, "passphrase": ""}, "/s", None))
    assert f"ssid={ssid.encode('utf-8').hex()}" in text
    assert text.count("}") == 1


class Recorder:
    """wpa_supplicant writes its pid file; wpa_cli says the state; dhcpcd and ip answer."""

    def __init__(self, joins=True, leases=True, gateway="192.0.2.1"):
        self.calls, self.joins, self.leases, self.gateway = [], joins, leases, gateway

    def __call__(self, argv, check=True):
        self.calls.append(list(argv))
        if argv[0] == "wpa_supplicant":
            with open(argv[argv.index("-P") + 1], "w", encoding="utf-8") as f:
                f.write(f"{os.getpid()}\n")
            with open(argv[argv.index("-f") + 1], "w", encoding="utf-8") as f:
                f.write("wlan1: Trying to associate\nwlan1: CTRL-EVENT-SSID-TEMP-DISABLED "
                        "reason=WRONG_KEY\n")
            return ""
        if argv[0] == "wpa_cli":
            return "wpa_state=COMPLETED\n" if self.joins else "wpa_state=SCANNING\n"
        if argv[0] == "dhcpcd" and "-x" not in argv and not self.leases:
            raise CommandFailed(argv, 1, "timed out")
        if argv[:2] == ["ip", "-4"] and "route" in argv:
            return (f"default via {self.gateway} proto dhcp src 192.0.2.9 metric 4000\n"
                    if self.gateway else "")
        return ""


def client(tmp_path, runner):
    return WifiClient(state_dir=str(tmp_path), runner=runner, is_wpa=lambda pid: True,
                      kill=lambda pid: None, sleep=lambda s: None, join_s=3)


def test_joining_runs_wpa_supplicant_then_dhcp_on_that_adapter_only(tmp_path):
    rec = Recorder()
    client(tmp_path, rec).start("wlan1", NET, "GB")
    progs = [c[0] for c in rec.calls]
    assert progs.index("wpa_supplicant") < progs.index("wpa_cli") < progs.index("dhcpcd")
    wpa = rec.calls[progs.index("wpa_supplicant")]
    assert wpa[wpa.index("-i") + 1] == "wlan1" and "-B" in wpa
    dhcp = rec.calls[progs.index("dhcpcd")]
    assert dhcp[-1] == "wlan1" and "-4" in dhcp and dhcp[dhcp.index("-m") + 1] == "4000"
    assert dhcp[dhcp.index("-c") + 1] == "/bin/true"  # no hook: resolv.conf and the rest alone
    for call in rec.calls:
        assert "wlan0" not in " ".join(call)
    conf = tmp_path / "wpa-wlan1.conf"
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(conf).st_mode) == 0o600


def test_joining_keeps_the_box_s_own_traffic_off_the_client(tmp_path):
    rec = Recorder()
    client(tmp_path, rec).start("wlan1", NET, None)
    sysctls = [c[-1] for c in rec.calls if c[0] == "sysctl"]
    assert "net.ipv4.conf.wlan1.arp_ignore=1" in sysctls
    assert "net.ipv4.conf.wlan1.arp_announce=2" in sysctls
    assert "net.ipv6.conf.wlan1.disable_ipv6=1" in sysctls


def test_the_gateway_the_network_gave(tmp_path):
    c = client(tmp_path, Recorder())
    assert c.gateway("wlan1") == "192.0.2.1"
    assert client(tmp_path, Recorder(gateway=None)).gateway("wlan1") is None


def test_a_network_not_joined_fails_with_wpa_supplicant_s_reason_and_leaves(tmp_path):
    rec = Recorder(joins=False)
    with pytest.raises(WifiClientFailed, match="wlan1 did not join upstream.*WRONG_KEY"):
        client(tmp_path, rec).start("wlan1", NET, None)
    assert not [c for c in rec.calls if c[0] == "dhcpcd" and "-x" not in c]
    assert not list(tmp_path.iterdir())


def test_no_address_from_the_network_fails_and_leaves(tmp_path):
    rec = Recorder(leases=False)
    with pytest.raises(WifiClientFailed, match="no address from upstream"):
        client(tmp_path, rec).start("wlan1", NET, None)
    assert ["dhcpcd", "-x", "-4", "wlan1"] in rec.calls
    assert not list(tmp_path.iterdir())


def test_leaving_twice_and_never_touching_an_adapter_it_did_not_join(tmp_path):
    rec = Recorder()
    c = client(tmp_path, rec)
    c.start("wlan1", NET, None)
    c.stop("wlan1")
    c.stop("wlan1")
    assert sum(call == ["dhcpcd", "-x", "-4", "wlan1"] for call in rec.calls) == 1
    rec.calls.clear()
    c.stop("eth0")  # a wired inbound: its own DHCP client is not wanpire's
    assert rec.calls == []
    assert not c.joined("wlan1")
