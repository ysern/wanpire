"""The access point on a Wi-Fi adapter: hostapd's settings, starting and stopping it. No root,
no radio: commands go to a recording runner."""

import os
import stat

import pytest

from wanpire.access_point import AccessPoint, AccessPointFailed, hostapd_settings
from wanpire.engine import CommandFailed

AP = {"ssid": "lab-ap", "passphrase": "correct horse"}


def lines(text):
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_the_settings_in_bridge_mode():
    text = lines(hostapd_settings("wlan1", AP, "GB", bridge="wpbr0"))
    for want in ("interface=wlan1", "bridge=wpbr0", "driver=nl80211", "hw_mode=a", "channel=36",
                 "country_code=GB", "ieee80211d=1", "ieee80211n=1", "ieee80211ac=1",
                 "vht_oper_chwidth=1", "vht_oper_centr_freq_seg0_idx=42", "wpa=2",
                 "wpa_key_mgmt=WPA-PSK SAE", "rsn_pairwise=CCMP", "ieee80211w=1",
                 "wpa_passphrase=correct horse", "sae_password=correct horse", "utf8_ssid=1",
                 f"ssid2={'lab-ap'.encode().hex()}"):
        assert want in text, want
    assert not [line for line in text if line.startswith("ssid=")]


def test_the_settings_in_router_mode_have_no_bridge():
    text = lines(hostapd_settings("wlan1", AP, "US"))
    assert not [line for line in text if line.startswith("bridge=")]
    assert "country_code=US" in text


def test_a_name_that_is_not_plain_text_is_written_in_hexadecimal():
    ssid = 'lab"ap\nchannel=1 é'
    text = lines(hostapd_settings("wlan1", {"ssid": ssid, "passphrase": "eight888"}, "GB"))
    assert f"ssid2={ssid.encode('utf-8').hex()}" in text
    assert "channel=1" not in [line for line in text if line != "channel=36"]
    assert sum(line.startswith("channel=") for line in text) == 1


class Recorder:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def __call__(self, argv, check=True):
        self.calls.append(list(argv))
        if self.fail and argv[0] == "hostapd":
            log = argv[argv.index("-f") + 1]
            with open(log, "w", encoding="utf-8") as f:
                f.write("wlan1: interface state UNINITIALIZED->COUNTRY_UPDATE\n"
                        "Could not set channel for kernel driver\n"
                        "wlan1: interface state COUNTRY_UPDATE->DISABLED\n")
            raise CommandFailed(argv, 1, "")
        if argv[0] == "hostapd":
            pid_file = argv[argv.index("-P") + 1]
            with open(pid_file, "w", encoding="utf-8") as f:
                f.write(f"{os.getpid()}\n")  # a process that exists, standing in for hostapd
        return ""


def test_start_writes_the_settings_readable_by_root_only_and_runs_hostapd(tmp_path):
    run = Recorder()
    ap = AccessPoint(state_dir=str(tmp_path), runner=run, is_hostapd=lambda pid: False)
    ap.start("wlan1", AP, "GB", bridge="wpbr0")
    conf = tmp_path / "hostapd-wlan1.conf"
    assert "bridge=wpbr0" in conf.read_text(encoding="utf-8")
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(conf).st_mode) == 0o600
    (argv,) = [c for c in run.calls if c[0] == "hostapd"]
    assert argv[1] == "-B" and str(conf) == argv[-1]
    assert argv[argv.index("-P") + 1] == str(tmp_path / "hostapd-wlan1.pid")


def test_hostapd_refusing_fails_with_its_reason(tmp_path):
    ap = AccessPoint(state_dir=str(tmp_path), runner=Recorder(fail=True),
                     is_hostapd=lambda pid: False)
    with pytest.raises(AccessPointFailed, match="Could not set channel"):
        ap.start("wlan1", AP, "GB")
    assert not (tmp_path / "hostapd-wlan1.conf").exists()


def test_stop_ends_hostapd_and_removes_its_files_and_twice_is_safe(tmp_path):
    killed = []
    ap = AccessPoint(state_dir=str(tmp_path), runner=Recorder(),
                     is_hostapd=lambda pid: pid not in killed,
                     kill=lambda pid: killed.append(pid))
    ap.start("wlan1", AP, "GB", bridge="wpbr0")
    assert ap.running("wlan1")
    ap.stop("wlan1")
    assert killed == [os.getpid()] and not ap.running("wlan1")
    assert not list(tmp_path.iterdir())
    ap.stop("wlan1")
    assert killed == [os.getpid()]


def test_start_twice_restarts_it(tmp_path):
    killed = []
    run = Recorder()
    ap = AccessPoint(state_dir=str(tmp_path), runner=run,
                     is_hostapd=lambda pid: pid not in killed,
                     kill=lambda pid: killed.append(pid))
    ap.start("wlan1", AP, "GB")
    ap.start("wlan1", AP, "GB")
    assert len([c for c in run.calls if c[0] == "hostapd"]) == 2 and len(killed) == 1


def test_no_command_names_the_control_adapter(tmp_path):
    run = Recorder()
    ap = AccessPoint(state_dir=str(tmp_path), runner=run, is_hostapd=lambda pid: False)
    ap.start("wlan1", AP, "GB", bridge="wpbr0")
    ap.stop("wlan1")
    assert not [c for c in run.calls if any("wlan0" in part for part in c)]
