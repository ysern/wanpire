## 1. Tests first

- [x] 1.1 Failing tests: `wanpire reset` clears every outbound adapter, never control
- [x] 1.2 Failing tests (staging root): a first install with roles; the files, the token's form and mode, the unit
- [x] 1.3 Failing tests: detection from a fake sysfs; no outbound port stops before any change
- [x] 1.4 Failing tests: the netplan drop-in in bridge and router mode
- [x] 1.5 Failing tests: idempotent; other roles on an installed box refused; dry run writes nothing; no root refused
- [x] 1.6 Failing tests: uninstall, with and without `--purge`

## 2. Build

- [x] 2.1 `wanpire reset`
- [x] 2.2 `install/install.sh` and `install/wanpire.service` until green

## 3. Close

- [x] 3.1 On the Pi: the tests; a real install with the roles on a namespace bed (a unit drop-in), the service up, the web page reached over Wi-Fi; uninstall leaves it clean
- [x] 3.2 Journal, open questions, README

## 4. No token (I6, the owner, 2026-10-11)

- [x] 4.1 Failing tests (staging root): no credential written; the last line points to the first visit; `--user` with the password on standard input writes the account hashed, mode 0600; a second run keeps it; an old token is removed
- [x] 4.2 `install/install.sh` until green
