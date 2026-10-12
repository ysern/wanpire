## Context

D10 of `design-the-link-emulator/design.md` sketches the install. The pieces it installs exist:
the server (`wanpire serve`, REST, web page and MCP), the modes (`wanpire up`, `down`), the
configuration's checks. The USB adapter is not here yet (O1), so the script must be testable
without a second Ethernet port, and it must never cut the control path while it works.

## Goals / Non-Goals

**Goals:** one POSIX shell script, idempotent, for Ubuntu Server and other Debian-like systems;
a systemd unit; a netplan drop-in; uninstall; tests that run without root and without the
hardware.

**Non-Goals:** first-boot steps (flashing, SSH keys, Wi-Fi credentials, the DHCP reservation);
systems without netplan (the script skips the drop-in and says what the ports need); TLS; a
Debian package.

## Decisions

### I1. A shell script, steps in order, each one idempotent

`install/install.sh [install|uninstall] [options]`, POSIX `sh` (dash on Ubuntu). Steps: check
(root, apt, Python 3.12+, the roles), packages, the venv, the configuration, the account (I6), the
netplan drop-in, the unit. Each step looks before it writes and writes only what differs, so a
second run changes nothing and says "unchanged" for each step.

Not taken: Ansible or a Debian package (more to learn for a one-box install); a Python installer
(it needs the venv it is meant to create).

### I2. Roles: given, or detected and checked by wanpire

`--control`, `--inbound`, `--outbound`, `--mode` name them. Otherwise the script reads
`/sys/class/net`: Wi-Fi (a `wireless` directory) as control; a wired port whose device is not on
USB as inbound; one on USB as outbound. Anything missing stops the script before it changes the
system. Once the venv exists, `wanpire adapters --config` checks the written file with wanpire's
own rules (outbound shares nothing, bridge ports are wired).

An existing configuration is never overwritten. Roles given that differ from it are refused,
saying to edit `/etc/wanpire/wanpire.json` (and run `wanpire down` first) or to uninstall with
`--purge`.

### I3. netplan: written, validated, not applied by default

`/etc/netplan/60-wanpire.yaml`, mode 0600, `renderer` left alone:

```yaml
network:
  version: 2
  ethernets:
    eth0: {dhcp4: false, dhcp6: false, accept-ra: false, link-local: [], optional: true}
    eth1: {dhcp4: false, dhcp6: false, accept-ra: false, link-local: [], optional: true}
```

Bridge mode names inbound and outbound; router mode only outbound (inbound keeps its address,
the NAT's way out). The control adapter is never named, so its configuration (often
`50-cloud-init.yaml`) is untouched. Later files override earlier keys, so `dhcp4: false` here
wins over a `dhcp4: true` there. The bridge itself is not in netplan: `wanpire up` makes it, so
the mode stays wanpire's configuration.

The script runs `netplan generate` to validate and stops there: applying restarts networking,
which on a box controlled over Wi-Fi is the one moment it could lose its own session. The change
takes effect at the next boot, or at once with `--apply-netplan`.

Not taken: the bridge in netplan (two sources of truth for the mode); applying by default.

### I4. The unit

```ini
[Unit]
Description=wanpire link emulator
Wants=network-online.target
After=network-online.target

[Service]
ExecStartPre=/opt/wanpire/venv/bin/wanpire reset
ExecStartPre=/opt/wanpire/venv/bin/wanpire up
ExecStart=/opt/wanpire/venv/bin/wanpire serve
ExecStopPost=/opt/wanpire/venv/bin/wanpire reset
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`wanpire reset` reads the configuration and clears each outbound adapter (the engine's clear
also stops a dead-man timer), whatever is on it. It runs at start, so a box rebooted with a link
applied comes up clean (D3), and after stop. `Restart=on-failure` covers a control address that
arrives after `network-online`. Root, as A10 says.

### I5. Tested against a staging root

`--root DIR` prefixes every path and skips apt, `systemctl` and `netplan`; `--sysfs DIR` points
detection at a fake `/sys/class/net`; `--no-venv` skips the venv (and the check that needs it). `--no-check`, with all three roles
named, installs without looking for the adapters: for a box whose USB port is not plugged in yet.
`tests/install/` runs the script that way in a temporary directory, without root, on any Linux:
files and their modes, detection, refusals, idempotence (a second run's files are byte-identical),
uninstall. `--dry-run` prints the steps and writes nothing.

The real install is then tried once on the Pi with its real paths and systemd, but with roles
on a namespace test bed through a unit drop-in, since the second port is missing; nothing touches
the real `eth0` or `wlan0` beyond the server listening on the control address.

### I6. No token: the account on the first visit, or given (revised, the owner, 2026-10-11)

The first version generated `/etc/wanpire/token` (64 hex digits, mode 0600) at install. The box
now has one account instead (R6 of `add-the-rest-api`), made on the first visit to its web page,
so the install writes no credential and ends by saying to open `http://<control-address>:8080/`
and make it. `--user NAME` sets it at install, the password read from standard input and handed
to `wanpire account set`, for a box that should not wait for a visit; the script never takes the
password as an argument, where `ps` and the shell's history would see it. A box that already has
an account keeps it; an old `/etc/wanpire/token` is removed. Under `--root` the account is
written by the staging venv's `wanpire account set --file`, so the tests see the same file.

Not taken: a random password printed at install (one more secret to copy off the console, which
the first visit already avoids); a default password (an open box until someone changes it).

## Risks / Trade-offs

- **The box is unclaimed from the install until the first visit.** → Anyone on the control
  network could make the account first. `--user` closes that window, and the script's last line
  says to visit at once.
- **A wrong role on a remote box** could bridge away its only wired path. → The control adapter
  may not be a bridge port (A26), detection stops when unsure, and netplan is not applied unless
  asked.
- **Systems without netplan** (Debian with ifupdown). → The script says which ports need no
  address and leaves it to the person.
