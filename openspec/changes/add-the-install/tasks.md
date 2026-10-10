## 1. Tests first

- [ ] 1.1 Failing tests: `wanpire reset` clears every outbound adapter, never control
- [ ] 1.2 Failing tests (staging root): a first install with roles; the files, the token's form and mode, the unit
- [ ] 1.3 Failing tests: detection from a fake sysfs; no outbound port stops before any change
- [ ] 1.4 Failing tests: the netplan drop-in in bridge and router mode
- [ ] 1.5 Failing tests: idempotent; other roles on an installed box refused; dry run writes nothing; no root refused
- [ ] 1.6 Failing tests: uninstall, with and without `--purge`

## 2. Build

- [ ] 2.1 `wanpire reset`
- [ ] 2.2 `install/install.sh` and `install/wanpire.service` until green

## 3. Close

- [ ] 3.1 On the Pi: the tests; a real install with the roles on a namespace bed (a unit drop-in), the service up, the web page reached over Wi-Fi; uninstall leaves it clean
- [ ] 3.2 Journal, open questions, README
