## 1. Spike: the USB adapter as an access point (on the box)

- [ ] 1.1 Find the chip from the USB id tables of the candidate drivers; check the driver's licence
- [ ] 1.2 Install the kernel headers, `dkms`, `hostapd`; build and install the driver by DKMS; the adapter gets a network interface, its radio lists AP mode
- [ ] 1.3 A test access point on the USB adapter only (5 GHz, WPA2/WPA3, a generated name and password): up, its channel and width, its beacon seen from the box's other radio
- [ ] 1.4 Station-less stability: the access point left up for an hour or more, checked every minute (hostapd alive, interface up, kernel log clean)
- [ ] 1.5 Record what needs a Wi-Fi client (association, WPA3, throughput, added delay and loss against the line) as questions for the owner
- [ ] 1.6 Take the test access point down; keep the driver if it works; findings in `spikes/usb-wifi-access-point.md`, the journal and the open questions. If it fails: stop here, recommend an adapter with an in-kernel driver

## 2. Configuration (no root)

- [ ] 2.1 Failing tests: each scenario of `adapter-roles` (Wi-Fi as an access point, radio without AP mode, Wi-Fi inbound in router mode, name and password rules, country, the wired configuration as before, writing it back)
- [ ] 2.2 Implement in `config.py` until green

## 3. The access point (no root)

- [ ] 3.1 Failing tests: the `hostapd` settings for bridge and router mode, the name in hexadecimal, the file's mode; start and stop with a fake runner, twice; hostapd's reason on failure; no command names the control adapter
- [ ] 3.2 Implement `access_point.py` and its place in `modes.py` until green

## 4. REST API

- [ ] 4.1 Failing tests: `GET /api/v1/roles` (the offered adapters), `PUT` refusing one adapter twice, bad Wi-Fi settings, 409 under a link or a lease, a saved change setting the mode up again, a failed set-up put back
- [ ] 4.2 Implement in `api.py` (a configuration that can change while the server runs) until green

## 5. The page

- [ ] 5.1 Failing browser tests: the two drop-downs, the Wi-Fi fields shown and hidden, the same adapter twice, a short password, saved
- [ ] 5.2 Implement in `index.html` and `app.js` until green; width and contrast tests still green

## 6. Install and close

- [ ] 6.1 Failing tests: `--wifi-driver --dry-run` prints the steps, the country from `--wifi-country`, an unrecognised adapter named
- [ ] 6.2 Implement in `install.sh` until green
- [ ] 6.3 On the box: the roles saved from the page with the USB adapter as outbound in bridge mode, the access point up, then put back as it was
- [ ] 6.4 README (the adapters known to work), journal, open questions
