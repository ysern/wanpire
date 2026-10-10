## Why

Today wanpire runs from a checkout with a token made by hand and a server started by hand. The
plan's B4 and the design's D10 ask for one script that turns Ubuntu Server on a Raspberry Pi, or
any Debian-like Linux with two Ethernet ports, into a wanpire box: the server started at boot,
the line's two ports without addresses, the control on Wi-Fi, impairments cleared at boot, and a
way back out.

## What Changes

- **`install/install.sh`**, idempotent, run as root from a checkout:
  - the packages (`python3-venv iproute2 nftables dnsmasq-base ethtool iw`);
  - a virtual environment in `/opt/wanpire/venv` with wanpire installed into it;
  - `/etc/wanpire/wanpire.json` with the roles given or detected (Wi-Fi as control, the
    on-board port as inbound, a USB port as outbound), checked by wanpire itself; kept if it
    exists;
  - `/etc/wanpire/token`, generated once, mode 0600;
  - a netplan drop-in, `/etc/netplan/60-wanpire.yaml`, giving the bridge's ports no address (in
    router mode, only the outbound port), leaving the control adapter's configuration as it is;
    validated with `netplan generate`, applied at the next boot or with `--apply-netplan`;
  - `wanpire.service`: clears every impairment, sets up the mode, then serves on the control
    address; enabled and started.
- **`install/install.sh uninstall`**: stops and removes the service, the drop-in and the
  virtual environment, and takes the mode down; `--purge` also removes `/etc/wanpire`.
- **`wanpire reset`**: clears every configured outbound adapter, for the service's start.
- **`--root DIR`** writes every file under a staging directory instead of `/`, and `--dry-run`
  only prints what would be done, so the script is tested without a second Ethernet port.

## Decided and assumed

Decided by the design (D3, D10) and the plan (B4): one idempotent script, a venv in
`/opt/wanpire`, the token at install, root under systemd, the bridge's ports address-less, the
control on Wi-Fi. Assumed here (also in `docs/open-questions.md`):

- the netplan drop-in is written and validated but not applied unless asked, because applying
  netplan restarts the network, the control path included;
- the service runs `wanpire reset` and `wanpire up` before serving, and restarts on failure (the
  control address may come late at boot);
- Python 3.12 or later is required; the script says so on an older system rather than building
  one;
- the configuration file is never overwritten; roles given on the command line for an existing
  file are refused with a message saying how to change it.

## Capabilities

### New Capabilities

- `install`: the script, its steps, its idempotence, the service and the way back out.

### Modified Capabilities

None (`wanpire reset` is part of the install's capability).

## Impact

- New `install/install.sh`, `install/wanpire.service`; `cli.py` gains `reset`.
- New `tests/install/` (Linux only, no root needed: the script runs against a staging root).
