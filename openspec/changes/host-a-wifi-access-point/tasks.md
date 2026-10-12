## 1. Spike: the USB adapter as an access point (on the box)

- [x] 1.1 Find the chip from the USB id tables of the candidate drivers; check the driver's licence
- [x] 1.2 Install the kernel headers, `dkms`, `hostapd`; build and install the driver by DKMS; the adapter gets a network interface, its radio lists AP mode (built with one compiler and a temporary swap file, after a power cycle; open question O6 answered)
- [x] 1.3 A test access point on the USB adapter only (5 GHz, WPA2/WPA3, a generated name and password): up, its channel and width, its beacon seen from the box's other radio
- [x] 1.4 Station-less stability: the access point left up for an hour or more, checked every minute (hostapd alive, interface up, kernel log clean)
- [x] 1.5 Record what needs a Wi-Fi client (association, WPA3, throughput, added delay and loss against the line) as questions for the owner
- [x] 1.6 Take the test access point down; keep the driver if it works; findings in `spikes/usb-wifi-access-point.md`, the journal and the open questions. If it fails: stop here, recommend an adapter with an in-kernel driver

## 2. Configuration (no root)

- [x] 2.1 Failing tests: each scenario of `adapter-roles` (Wi-Fi as an access point, radio without AP mode, Wi-Fi inbound in router mode, name and password rules, country, the wired configuration as before, writing it back)
- [x] 2.2 Implement in `config.py` until green

## 3. The access point (no root)

- [x] 3.1 Failing tests: the `hostapd` settings for bridge and router mode, the name in hexadecimal, the file's mode; start and stop with a fake runner, twice; hostapd's reason on failure; no command names the control adapter
- [x] 3.2 Implement `access_point.py` and its place in `modes.py` until green

## 4. REST API

- [x] 4.1 Failing tests: `GET /api/v1/roles` (the offered adapters), `PUT` refusing one adapter twice, bad Wi-Fi settings, 409 under a link or a lease, a saved change setting the mode up again, a failed set-up put back
- [x] 4.2 Implement in `api.py` (a configuration that can change while the server runs) until green

## 5. The page

- [x] 5.1 Failing browser tests: the two drop-downs, the Wi-Fi fields shown and hidden, the same adapter twice, a short password, saved
- [x] 5.2 Implement in `index.html` and `app.js` until green; width and contrast tests still green

## 6. Install and close

- [x] 6.1 Failing tests: `--wifi-driver --dry-run` prints the steps, the country from `--wifi-country`, an unrecognised adapter named
- [x] 6.2 Implement in `install.sh` until green (the install tests pass on the box)
- [ ] 6.3 On the box: the roles saved from the page with the USB adapter as outbound in bridge mode, the access point up, then put back as it was (not done: it re-sets the running line, which carries the owner's traffic; open question O9)
- [x] 6.4 README (the adapters known to work), journal, open questions

## 7. A Wi-Fi inbound adapter is a client, in router mode (the owner, 2026-10-11)

- [x] 7.1 Revise the proposal, the design (D3 revised, D7), the specs (`adapter-roles`, `web-ui`, `rest-api`, `access-point`, `install`; `wifi-client` new) and the open questions
- [x] 7.2 Failing tests: a Wi-Fi inbound in router mode with its network; refused in bridge mode with why; its network required, an access point not standing in for it; its password rules (8 to 63, 64 hexadecimal, empty); the control adapter never joined
- [x] 7.3 Implement in `config.py` until green
- [x] 7.4 Failing tests: `wpa_supplicant`'s settings (WPA2+WPA3, the 64-digit key, open, the name in hexadecimal); joining, the address by DHCP with no hook and a high metric, ARP and IPv6 kept off the client; a network not joined and no address failing with the reason; leaving twice; a wired inbound left alone; the line routed out through the client in router mode, and the rule removed
- [x] 7.5 Implement `wifi_client.py` and its place in `modes.py` until green
- [x] 7.6 Failing tests and implementation: `GET`/`PUT /api/v1/roles` with `wifi_clients`; the page's *Network to join* under a Wi-Fi inbound, refused in bridge mode, its password rules, an open network saved
- [x] 7.7 The install adds `wpasupplicant` and `dhcpcd-base`; the README
- [x] 7.8 On the box: the USB adapter joins a network as a client by `wifi_client.py`, takes an address and a gateway, the control adapter untouched; then leaves (the line's routing rule not tried there: the outbound adapter is a port of the running bridge; O9)
