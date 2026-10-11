## Why

A device under test is often wireless: a headset, a phone, a tablet. Today it reaches wanpire
only through a wired port, so a wireless device needs an access point of its own behind the box,
which adds a hop wanpire does not control. A USB Wi-Fi adapter on the box can be that access
point itself: the device joins wanpire's own network, and every impairment applies to it.

The roles are set today by editing `/etc/wanpire/wanpire.json` over SSH, and the web page's
Adapters page only lists them. Setting the line's two adapters from the page, with the access
point's name and password beside a Wi-Fi one, makes the box usable without a shell.

## What Changes

- **A Wi-Fi adapter in the inbound or the outbound role is an access point.** wanpire runs
  `hostapd` on it, on 5 GHz, WPA2/WPA3-Personal, with a network name and a password from the
  configuration and a regulatory country. In bridge mode the access point is a port of the
  bridge; in router mode the outbound access point carries the router's network and its DHCP.
  The rule "a Wi-Fi outbound adapter is refused until access-point mode is built" is lifted.
- **The control adapter is never an access point**, and a Wi-Fi adapter whose radio cannot be an
  access point is refused.
- **The configuration** gains `access_points` (per adapter: `ssid` and `passphrase`) and
  `wifi.country`. Both are optional; a configuration without them loads as before.
- **The REST API** gains `GET` and `PUT /api/v1/roles`: read the inbound and outbound adapters
  and their access points, and change them. A change is validated, written to the
  configuration, and the mode is set up again with it. It is refused while a link is applied or
  a lease is held.
- **The web page's Adapters / Roles page** becomes a form: two drop-downs, *Inbound adapter* and
  *Outbound adapter*, offering every adapter but virtual ones and the control adapter when it is
  Wi-Fi. Picking a Wi-Fi adapter shows its *Network name* and *Password* below it. *Save*
  checks them by the general Wi-Fi rules and refuses one adapter in both roles, then sends them.
  The adapters' table stays below.
- **The install** offers, for a USB Wi-Fi adapter that has no driver, an optional step that
  builds and installs the out-of-tree driver through DKMS (`--wifi-driver`). wanpire references
  the driver's repository and never vendors it. The README lists the adapters known to work.
- **A spike comes first** (task group 1): the owner's adapter, a TP-Link Archer TX20U Plus
  (USB `2357:013f`), has no driver in the box's kernel. The spike installs the out-of-tree driver,
  proves access-point mode with `hostapd` on 5 GHz with WPA2/WPA3, and runs it for a while. If it
  fails, this change stops after the spike and recommends an adapter whose driver is in the
  kernel and does access-point mode (MediaTek MT7612U or MT7921AU).

## Decided and assumed

Decided by the owner (2026-10-11): the access point; the two drop-downs with the network name and
password shown only for a Wi-Fi adapter; Save validating and refusing one adapter in both roles;
the name is the SSID (1 to 32 bytes) and the password is WPA2/WPA3-Personal (8 to 63 printable
ASCII characters); a Wi-Fi adapter picked as inbound or outbound becomes an access point, in
bridge or router mode; 5 GHz with a regulatory country in the configuration; the out-of-tree
driver tried by a spike first, installed as an optional step, referenced and not vendored.

Assumed here (also in `docs/open-questions.md`, A61 to A70): the chip and driver the spike found
(the TX20U Plus is an RTL8832AU, driven by the `rtw89` backport, not the `rtl8852bu` first
guessed); channel 36 at 80 MHz; WPA2 and WPA3 in transition mode with protected management
frames optional; the drop-downs leave out the control adapter only when it is Wi-Fi; a Wi-Fi
inbound adapter is accepted in bridge mode only; Save sets the mode up again at once and is
refused while a link is applied or a lease is held; the password is stored in the configuration
file, readable by root only, and shown on the page; the country is set in the configuration or
by the install, not on the page.

## Capabilities

### New Capabilities

- `access-point`: running an access point on a Wi-Fi adapter in a role, and taking it down.

### Modified Capabilities

- `adapter-roles`: a Wi-Fi adapter in a role is an access point; the configuration's access
  points and country, and their rules.
- `rest-api`: reading and changing the roles.
- `web-ui`: the Adapters / Roles page sets the two roles.
- `install`: the optional driver step.

## Impact

- New: `src/wanpire/access_point.py`; tests in `tests/unit`.
- Changed: `config.py` (access points, country, the Wi-Fi rules, writing the file), `modes.py`
  (the access point in each mode), `api.py` (`/api/v1/roles`, a configuration that can change
  while the server runs), `web/index.html`, `web/app.js`, `install/install.sh`, README.
- The box needs `hostapd`; the driver step needs the kernel's headers, `dkms`, `git` and a
  compiler. Nothing changes for a box without a Wi-Fi adapter in a role.
- Archive after `set-up-the-modes`, `add-the-rest-api`, `add-the-web-ui` and `add-the-install`,
  whose specs this change modifies.
