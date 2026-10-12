## Context

wanpire's line runs through two adapters, inbound and outbound, joined in a bridge or routed with
NAT (`set-up-the-modes`). The reference box is controlled over its built-in Wi-Fi, so that radio
is taken. A second radio, on USB, can be an access point for a wireless device under test. The
owner's adapter is a TP-Link Archer TX20U Plus (USB `2357:013f`), which Ubuntu 24.04's kernel
(6.8) does not drive: its `rtw89` has PCIe modules only.

## Goals / Non-Goals

**Goals:** a Wi-Fi adapter's role by its side (the owner, 2026-10-11): outbound, an access point
on a USB Wi-Fi adapter, in either mode; inbound, a Wi-Fi client of a network of the wider world,
in router mode; the roles set from the web page and the REST API; the out-of-tree driver as an
optional install step; a spike that proves the adapter first.

**Non-Goals:** the box's control channel moving off its Wi-Fi; 2.4 GHz or a channel picker;
several access points on one radio; WPA-Enterprise, for the access point or the client; hidden
networks; a Wi-Fi client inbound in bridge mode (a client cannot be a bridge port: D7).

## Decisions

### D1. The driver: the `rtw89` backport, by DKMS, referenced and not vendored

The spike looked the adapter up in the USB tables of the candidate drivers. `2357:013f` is in
neither of morrownr's Realtek vendor drivers (`rtl8852bu`, `rtl8852cu`); it is in upstream
Linux's `rtw8852au.c`, so the chip is an **RTL8832AU**, not the RTL8852BU first guessed. Ubuntu
24.04's 6.8 kernel predates rtw89's USB support. The `rtw89` backport (github.com/morrownr/rtw89,
"Dual BSD/GPL", kernel 6.6 and newer, DKMS) carries the upstream USB drivers, 8852AU among them.

- *Chosen:* the backport, installed by DKMS so a kernel update rebuilds it. It is the upstream
  driver (mac80211, so `hostapd` and `iw` work as with any in-kernel driver), and DKMS keeps it
  across kernel updates.
- *Not taken:* the Realtek vendor driver for 8852AU (lwfinger's `rtl8852au`, last changed in
  2024, its own wireless stack, AP mode of uneven repute); waiting for a kernel with rtw89 USB
  (Ubuntu's 26.04 LTS); vendoring the driver into wanpire (GPL code in an MIT repository, and a
  copy that would fall behind).
- The install fetches it from its repository by `git`, at a pinned commit that the spike
  proved, and builds it on the box. wanpire ships no line of it.

### D2. `hostapd`, started by wanpire, one per access point

`hostapd` is the standard Linux access point. wanpire writes its settings to
`/run/wanpire/hostapd-<adapter>.conf` (mode 600) and runs it in the background with a pid file,
as it runs `dnsmasq`. *Not taken:* Ubuntu's `hostapd.service` (one fixed file in `/etc`, a second
owner of the same state); NetworkManager's hotspot (not on Ubuntu Server, and it would also
manage the control adapter).

Settings: `hw_mode=a`, `channel=36`, `ieee80211n=1`, `ieee80211ac=1`, `vht_oper_chwidth=1`
(80 MHz, centre 42), `country_code` and `ieee80211d=1`; `wpa=2`, `wpa_key_mgmt=WPA-PSK SAE`,
`rsn_pairwise=CCMP`, `ieee80211w=1` (protected management frames optional, so WPA2-only devices
join), `sae_require_mfp=1`; the name as `ssid2=` in hexadecimal with `utf8_ssid=1`, so no
character in it can end the line. In bridge mode, `bridge=wpbr0`, and `hostapd` puts the
adapter in the bridge itself. Channel 36 is a non-DFS channel allowed in nearly every country,
so the access point starts at once with no radar check. *Not taken:* `ieee80211ax` (the chip
supports Wi-Fi 6, but Ubuntu's `hostapd` 2.10 and the driver's AP mode are less proven with it;
a later option); automatic channel selection (needs a scan and makes runs unrepeatable); 160 MHz
(DFS channels, radar waits).

### D3. A Wi-Fi adapter's role depends on its side

*Revised by the owner, 2026-10-11.* A Wi-Fi **outbound** adapter is an access point, in either
mode. A Wi-Fi **inbound** adapter is a client of a network of the wider world (D7), in router
mode only. The configuration gains:

```json
{"schema": "wanpire-config/1", "mode": "router",
 "adapters": {"control": "wlan0", "inbound": "wlan1", "outbound": ["wlan2"]},
 "wifi_clients": {"wlan1": {"ssid": "<network-to-join>", "passphrase": "<its-password>"}},
 "access_points": {"wlan2": {"ssid": "<wifi-ssid>", "passphrase": "<wifi-password>"}},
 "wifi": {"country": "GB"}}
```

The schema stays `wanpire-config/1`: the three keys are optional, and an older configuration
loads unchanged. A Wi-Fi outbound adapter needs its access point, a radio that does AP mode, and
the country. A Wi-Fi inbound adapter needs its network to join, whose password is 8 to 63
printable ASCII characters, 64 hexadecimal digits (the WPA2 key itself), or empty (an open
network); it needs neither AP mode nor the country (the regulatory domain the box already has
governs a client). An access point named for the inbound adapter does not count as its network.

*Superseded:* the first version of this decision, that a Wi-Fi adapter in either role is an
access point and a Wi-Fi inbound one works in bridge mode only. It assumed an access point on the
inbound side, which the owner did not want. *Not taken:* a role `access-point` beside inbound and
outbound (the owner's page has two drop-downs, not three).

### D4. Saving the roles sets the mode up again, while the line is idle

`PUT /api/v1/roles` validates the new roles against the adapters, then, only if no link is applied
and no lease is held: takes the mode down with the old roles, writes the file (a temporary file
renamed over it, mode 600), and sets the mode up with the new ones. If set-up fails, it takes the
new set-up down, writes the old file back and sets the old mode up again, and answers 500 with
the reason. The server holds its configuration in one place that the engine's adapter, the
broker's clear and the status all read, so no restart is needed (a restart would end every
signed-in session). *Not taken:* writing the file and asking for a restart (the page would sign
everyone out); changing roles under a lease (the holder's link would move to another adapter
under them).

### D5. The page

Two `<select>`s, each followed by a Wi-Fi block shown only for a Wi-Fi adapter: under inbound,
*Network to join* and its *Password* (empty for an open network); under outbound, the access
point's *Network name* and *Password*. Passwords are shown as text, as a home router's page
shows its Wi-Fi password, so the access point's can be read off to the device. Its validation is
the server's, repeated in the page so a mistake is shown beside the field before anything is
sent (a Wi-Fi inbound in bridge mode included); the server stays the authority. *Not taken, for
now:* a scan of nearby networks offered as suggestions for *Network to join* (the radio must be
up as a client to scan, which it is not while it is an access point or unused, and a typed name
works; a later option). *Save* is the section's one primary button.
The adapters' table stays below. The country is not on the page: it is set once per box, by the
install or the file. *Not taken:* a password field that hides what is typed (the point is to
type it into a headset next); a country drop-down (one more field, set once).

### D6. The install's driver step

`install.sh --wifi-driver` installs `linux-headers-$(uname -r)`, `dkms`, `git` and
`build-essential`, clones the backport at its pinned commit into `/usr/src/rtw89-<version>`, runs
`dkms install`, installs its firmware and its `modprobe.d` file (which blacklists the in-kernel
`rtw89` PCIe modules: harmless on a Pi, which has none, and needed on a PC whose in-kernel ones
would clash). It recognises the adapters by the USB ids the backport lists, read from the cloned
source, so wanpire keeps no copy of the list. Without the option it only says an adapter has no
driver. *Not taken:* installing the driver by default (a kernel module built from a third party's
repository is the owner's choice); a prebuilt module (tied to one kernel).

### D7. A Wi-Fi inbound client, in router mode only

**Router mode only, the owner's answer (2026-10-11).** An access point drops frames from any
source address but its associated client's own (three-address 802.11), so a Wi-Fi client cannot
carry a bridge's other hosts. *Not taken:* a 4-address (WDS) client, which works only against an
access point that accepts it; a pseudo-bridge (proxy ARP and a DHCP relay), which breaks
broadcast, multicast and IPv6, and could be a later change of its own.

**wanpire runs the client itself**, as it runs `hostapd` and `dnsmasq`: `wpa_supplicant -B -D
nl80211 -i <adapter>` with its settings in `/run/wanpire/wpa-<adapter>.conf` (mode 600) and its
own control directory, then `dhcpcd -4` for that adapter only. *Not taken:* netplan's `wifis:`
(`netplan apply` regenerates and re-applies every interface, the control adapter's
`wpa_supplicant` included); systemd-networkd (its reload is the same risk, and it does not run in
the test bed's network namespaces).

- **Security:** WPA2-Personal and WPA3-Personal both offered (`key_mgmt=WPA-PSK WPA-PSK-SHA256
  SAE`, protected management frames optional), the 64-digit key for WPA2 only (SAE needs the
  password itself), and `key_mgmt=NONE` when the password is empty. The name is written in
  hexadecimal; a quoted password ends at its last quote and has no line break. No Enterprise, no
  hidden network (`scan_ssid=0`).
- **Joining is checked** with `wpa_cli status` for `wpa_state=COMPLETED`, up to 30 s; else the
  set-up fails with `wpa_supplicant`'s last lines (a wrong key shows there).
- **The box's own traffic stays on control,** even with the client on the same network as the
  control adapter: `dhcpcd` runs with no hook (`-c /bin/true`, so `resolv.conf` is left alone)
  and route metric 4000 (networkd gives 100 wired, 600 Wi-Fi), the adapter answers ARP for its own
  addresses only (`arp_ignore=1`, `arp_announce=2`, or the network could learn the control
  adapter's address at the client's MAC), and it has no IPv6 (a router advertisement would give
  it a default route).
- **The line leaves through the client** by a table and a rule of its own (`4077`): `default via
  <the gateway dhcpcd got> dev <inbound> table 4077` and `ip rule add iif <outbound> lookup 4077`.
  The box's own default route stays on control. No gateway fails the set-up. A wired inbound is
  unchanged: its system-managed route already wins by metric.
- **Leaving** (`dhcpcd -x`, then `wpa_supplicant` stopped, the files removed) happens only for an
  adapter wanpire joined, so a wired inbound's own DHCP client is never touched.

## Risks / Trade-offs

- **The driver is out of tree.** A kernel update the backport does not build against leaves the
  adapter without a driver until it catches up; DKMS reports it at the update. Mitigation: the
  pinned commit, and the README's list names the kernel it was proven on.
- **Wi-Fi adds its own delay, jitter and loss** before wanpire's impairments, unlike a wired port.
  The spike measures what it can from the box; the rest needs a client (open question).
- **The adapter's USB mode.** The backport switches the adapter to USB 3 by default; on a USB 2
  port it stays at 480 Mbit/s, which caps the access point well under its radio's rate.
- **The passwords sit in `/etc/wanpire/wanpire.json`,** root only, and are shown on the page to
  anyone signed in, like a router's: the access point's, and the network to join's.
- **The access point shares the control link's air** when the control adapter's network is on
  the same 80 MHz block (on the reference box it is: channel 40 against the access point's 36).
  Both still work; they take turns on the air. A channel option would be a later change.
- **A Wi-Fi client inbound depends on the network it joins:** its own delay, loss and rate come
  before wanpire's impairments, as the access point's do (open question O7).

## Measurements

The spike's findings are in [`spikes/usb-wifi-access-point.md`](spikes/usb-wifi-access-point.md).
