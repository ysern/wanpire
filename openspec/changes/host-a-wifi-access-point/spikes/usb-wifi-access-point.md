# Spike: the USB Wi-Fi adapter as an access point

**Status:** passed, 2026-10-12. The driver builds and loads, the adapter runs a 5 GHz WPA2/WPA3
access point that stayed up for an hour with no client, and joins a network as a client. What
needs a Wi-Fi device on the other side is the owner's (`docs/open-questions.md`, O7).

## Question

Can the owner's USB Wi-Fi adapter, a TP-Link Archer TX20U Plus (USB `2357:013f`), run a 5 GHz
WPA2/WPA3 access point with `hostapd` on the reference box (Raspberry Pi 4, 1 GB, Ubuntu 24.04,
kernel 6.8.0-raspi), steadily, through an out-of-tree driver?

## Why it matters

The change's access point rests on it. If it fails, the change stops here and recommends an
adapter whose driver is in the kernel and does AP mode.

## Rests on

- The kernel's `rtw89` on this box has PCIe modules only: no network interface appears for the
  adapter.
- The box is controlled over its built-in Wi-Fi: nothing in the spike may touch that radio's
  configuration, and the bridged line is left alone.

## Method

1. Find the chip from the USB id tables of the candidate drivers, and the licence.
2. Install the kernel headers, `dkms` and `hostapd`; build and install the driver by DKMS; check
   the adapter gets an interface and its radio lists AP mode.
3. Start `hostapd` by hand on the USB adapter only, with a generated test name and password, 5 GHz
   channel 36 at 80 MHz, WPA2 and WPA3; check it with `iw` and look for its beacon from the
   box's other radio.
4. Leave it up for an hour or more, checking every minute.
5. Take it down; keep the driver if it works.

## Kill or pivot signal

No interface, no AP mode in the radio's modes, `hostapd` failing to start on 5 GHz, or the
access point falling over within the hour: the out-of-tree route is dropped, and the change
recommends a MediaTek MT7612U or MT7921AU adapter (in-kernel `mt76`, AP mode proven).

## Findings

- The TX20U Plus (`2357:013f`) is an **RTL8832AU**. Its driver is the `rtw89` backport
  (morrownr/rtw89, Dual BSD/GPL, DKMS, kernels 6.6 and newer), not the `rtl8852bu` first guessed.
- **Building it with the backport's default of three compilers starves a 1 GB Pi**: SSH stopped
  answering within two minutes and had not come back 100 minutes later (ping still answered).
  The install builds with one compiler on a small box, also for DKMS's rebuild after a kernel
  update (`/etc/dkms/rtw89.conf`).
- **After the owner's power cycle, it built with one compiler in about ten minutes**, with a
  temporary 2 GB swap file on the SD card as a guard (barely touched: 1 MB at most; the box
  kept 400 MB or more available), removed afterwards. SSH answered throughout.
- **The module loads and the adapter works:** `rtw89_8852au_git` takes firmware 0.13.36.2 and
  switches the adapter from its USB 2 to its USB 3 identity; on the Pi's USB 2 port it stays at
  480 Mbit/s (O8). The interface lists AP mode and 5 GHz channels 36 to 48 at 23 dBm.
- **The access point, started by wanpire's own `access_point.py`,** came up on channel 36 at
  80 MHz (centre 42) after hostapd's 40 MHz neighbour scan, and was seen from the box's built-in
  radio as `[WPA2-PSK+SAE-CCMP][ESS][UTF-8]` at -20 dBm.
- **It stayed up for an hour with no client**, checked every minute: hostapd alive, interface
  up, channel and width unchanged, nothing from the driver in the kernel log. The one kernel
  message was the Pi's own undervoltage warning, gone in two seconds (O10).
- **It shares the control link's 80 MHz block** on the reference box (the control network is on
  channel 40): both work, taking turns on the air.
- **The country:** the Pi's built-in radio reports a code of its own ("98") as the global
  regulatory domain; the country the system asked for is in the kernel's `ieee80211_regdom`, and
  the install now reads it from there when `iw reg get` names none.

## Findings in full

### The chip is an RTL8832AU, not an RTL8852BU

The guess was morrownr's `rtl8852bu` (Realtek's vendor driver). Its supported-ids list and its
USB table do not carry `2357:013f`; nor do those of `rtl8852cu`. Upstream Linux's
`drivers/net/wireless/realtek/rtw89/rtw8852au.c` does, beside `2357:0140` and `2357:0141`: the
adapter is an RTL8832AU (the 2x2 Wi-Fi 6 chip of the 8852A family, on USB). Upstream's rtw89 has
had USB support only since kernels well after 6.8.

The backport of upstream's rtw89 (github.com/morrownr/rtw89) builds for kernels 6.6 and newer,
lists the RTL8832AU among its USB chips, carries the same `2357:013f` entry, and installs by DKMS.
Its modules are `MODULE_LICENSE("Dual BSD/GPL")`; the firmware is under Realtek's
redistribution licence (`LICENCE.rtlwifi_firmware.txt`). Installing it on a box is fine; copying
it into wanpire is not, and wanpire does not.

The adapter enumerates on the Pi as a USB 2.0 device (480 Mbit/s, vendor-specific class, 500 mA),
after its own switch out of its driver-disc mode.

### Building the driver on a 1 GB Pi starves it

The kernel headers, `dkms`, `git`, `build-essential` and `hostapd` installed cleanly (Ubuntu's
`hostapd` 2.10 comes masked, so it starts nothing by itself). The backport, version 7.3 at commit
`8bbbaca` (2026-10-05), was cloned into `/usr/src/rtw89-7.3` and `dkms install rtw89/7.3` started.

Within two minutes the box stopped answering SSH: the TCP connection opened, the SSH banner never
came, and it kept answering ping. The backport's Makefile runs `nproc - 1` compilers, three on a
Pi 4, and the rtw89 sources (large register tables) need more memory per compiler than a 1 GB
box with no swap has for three. The kernel does not kill anything; it keeps evicting and
re-reading pages, and nothing in user space gets to run. This is the box's control channel lost
by a build, not by a network change.

Consequences for the change: the install's driver step runs the build with one compiler on a box
with less than 3 GB (`NPROC=1`, which the Makefile takes from the environment), and says so. A
temporary swap file during the build is the other remedy (not taken: it writes a gigabyte to the
SD card).

### The build, again, with one compiler

`dkms remove rtw89/7.3 --all`, then `dkms install` run detached (`systemd-run`) with
`NPROC=1` and the same override the install writes to `/etc/dkms/rtw89.conf`. One `cc1` at a
time; every two minutes the box had 400 to 560 MB available and used at most 1 MB of the
temporary swap. All modules (the USB and the PCIe ones, since the Pi's kernel has PCI) built
and installed in about ten minutes. The firmware from the backport (`make install_fw`, which
compresses it to match the box's) and its `modprobe.d` file followed, as the install does them.
The swap file was a guard, not a need, once the build ran one compiler; the install does not
add one.

### The access point

wanpire's `AccessPoint` wrote the settings and started `hostapd` on the USB adapter only, with a
generated test name and password that were never written anywhere else. hostapd went
`COUNTRY_UPDATE`, `HT_SCAN`, `ENABLED`. `iw dev` showed type AP, channel 36 (5180 MHz), width
80 MHz, centre 5210 MHz; `hostapd_cli status` showed `ieee80211ac=1`, `vht_oper_chwidth=1`, two
spatial streams. One scan from the built-in radio, through its own `wpa_supplicant`, listed the
beacon with WPA2-PSK and SAE. The watch then ran 65 times a minute apart; every line read
`hostapd=yes state=ENABLED oper=up ch=36/80`.

### The client role

After the owner's change (a Wi-Fi inbound adapter is a client, in router mode), the adapter was
joined by wanpire's own `WifiClient` to the very network the control adapter is on, the hardest
case for keeping the control session where it is. It joined and had an address in 18 s, at
Wi-Fi 6 rates (80 MHz, two streams, 865 Mbit/s link rate at -54 dBm), and pinged its gateway
with no loss. The box's own default route stayed on the built-in radio (metric 600 against the
client's 4000), its route to the outside still went that way, the client had no IPv6 address,
answered ARP for its own address only, and `resolv.conf` was untouched; SSH over the built-in
radio never stalled. Leaving (twice) stopped its `wpa_supplicant` and `dhcpcd`, removed its
address, routes and files, and left the control adapter associated. A ten-minute timer was armed
first to take the adapter down had the session been lost; it was not needed. `dhcpcd` with no
configuration file (`-f /dev/null`) still asks for and installs the gateway. The line's own
routing rule (router mode with outbound) was not tried on the box: the outbound adapter is a port
of the running bridge.
