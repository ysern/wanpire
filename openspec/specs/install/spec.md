# install Specification

## Purpose
One script that makes a Debian-like Linux box with two Ethernet ports into a wanpire box, and
takes it back out.

## Requirements

### Requirement: The install writes the box's files

Run as root, `install/install.sh` SHALL install the packages, a virtual environment with
wanpire in `/opt/wanpire/venv`, the configuration `/etc/wanpire/wanpire.json`, the netplan
drop-in `/etc/netplan/60-wanpire.yaml` and the unit `wanpire.service`, and SHALL enable and start
the unit. It SHALL write no credential unless asked: the box's account is made on the first visit
to its web page. With `--user NAME` it SHALL set the account itself, reading the password from
standard input, and SHALL then say so instead of pointing to the first visit.

#### Scenario: A first install, roles given
- **GIVEN** a box with `wlan0`, `eth0` and `eth1`
- **WHEN** the script runs with `--control wlan0 --inbound eth0 --outbound eth1`
- **THEN** the configuration maps those roles in bridge mode, no account exists, the unit is
  enabled, and the script ends by saying to open the box's web page to make the account

#### Scenario: The account given to the install
- **GIVEN** a box with `wlan0`, `eth0` and `eth1`
- **WHEN** the script runs with the roles and `--user admin`, the password on standard input
- **THEN** `/etc/wanpire/account` holds `admin` and a hash of the password, never the password, in mode 0600

### Requirement: The roles are detected when not given

Without roles, the script SHALL propose the Wi-Fi adapter as control, the on-board Ethernet port
as inbound and a USB Ethernet port as outbound, and SHALL stop with a message naming what is
missing when it cannot find one.

#### Scenario: No second port
- **GIVEN** a box with only `wlan0` and `eth0`
- **WHEN** the script runs without roles
- **THEN** it stops before changing anything, saying no outbound port was found and how to name
  one

### Requirement: The bridge's ports get no address, the control is left alone

The netplan drop-in SHALL give the inbound and outbound ports (in router mode, the outbound port
only) no address: no DHCP, no router advertisements, no link-local address. It SHALL not name the
control adapter. The script SHALL not apply it unless asked with `--apply-netplan`.

#### Scenario: Bridge mode
- **GIVEN** the roles `wlan0`, `eth0`, `eth1` in bridge mode
- **WHEN** the script runs
- **THEN** the drop-in names `eth0` and `eth1` with `dhcp4: false` and `dhcp6: false`, and does
  not name `wlan0`

#### Scenario: Router mode
- **GIVEN** the roles `wlan0`, `eth0`, `eth1` in router mode
- **WHEN** the script runs
- **THEN** the drop-in names `eth1` only

### Requirement: Impairments are cleared at boot

The unit SHALL run `wanpire reset`, which clears every configured outbound adapter, then
`wanpire up`, before it serves; it SHALL restart the server when it fails. A line adapter that is
not plugged in SHALL NOT fail the unit: `reset` and `up` SHALL both exit 0 with it missing, so the
server starts with the line down and the page can say so.

#### Scenario: The unit
- **GIVEN** the unit written by the script
- **WHEN** it is read
- **THEN** `wanpire reset` runs before `wanpire up`, both before `wanpire serve`

#### Scenario: Reset
- **GIVEN** a configuration with outbound `eth1`
- **WHEN** `wanpire reset` runs
- **THEN** the engine clears `eth1`, and the control adapter is never touched

#### Scenario: The outbound adapter is unplugged at boot
- **GIVEN** a configuration with outbound `wlx1`, which the box does not have at boot
- **WHEN** the unit's pre-start steps run
- **THEN** both exit 0, `up` saying the line waits for `wlx1`, and the server is started

### Requirement: The install is idempotent

A second run with the same arguments SHALL change no file, and SHALL keep the existing account
and configuration; `--user` on a box that has an account SHALL leave it alone and say how to
change it (`wanpire account set`). An upgrade from a box with `/etc/wanpire/token` SHALL remove
the token, which nothing reads any more.

#### Scenario: Run twice
- **GIVEN** a box installed once, its account made on the first visit
- **WHEN** the script runs again with the same arguments
- **THEN** every file it wrote is byte for byte the same, and the account is untouched

#### Scenario: Other roles on an installed box
- **GIVEN** a box installed with outbound `eth1`
- **WHEN** the script runs again with `--outbound eth2`
- **THEN** it stops, saying the configuration exists and how to change it, and changes nothing

### Requirement: Uninstall takes it back out

`install/install.sh uninstall` SHALL stop and remove the unit, take the mode down, and remove the
drop-in and the virtual environment; with `--purge` it SHALL also remove `/etc/wanpire`.

#### Scenario: Uninstall keeps the configuration
- **GIVEN** an installed box
- **WHEN** `uninstall` runs without `--purge`
- **THEN** the unit, the drop-in and `/opt/wanpire` are gone and `/etc/wanpire` is kept

### Requirement: The script can be tried without changing the system

With `--root DIR` the script SHALL write under `DIR` instead of `/` and SHALL call no package
manager, `systemctl` or `netplan` there; with `--dry-run` it SHALL print each step and change
nothing. It SHALL refuse to run without root unless one of them is given.

#### Scenario: Dry run
- **GIVEN** any box
- **WHEN** the script runs with `--dry-run`
- **THEN** it prints the steps and no file exists afterwards that did not before

### Requirement: A Wi-Fi adapter's driver is an optional step

The install SHALL install `hostapd` (an access point), `wpasupplicant` and `dhcpcd-base` (a Wi-Fi
inbound client) with the box's other packages. When asked with
`--wifi-driver`, and only then, it SHALL build and install, through DKMS, the out-of-tree driver
for a USB Wi-Fi adapter that the box's kernel does not drive, fetched from the driver's own
repository and never shipped with wanpire, with the kernel headers, `dkms`, `git` and a compiler
it needs. It SHALL leave the box's built-in Wi-Fi and its driver alone. Without `--wifi-driver`,
an adapter it recognises with no driver SHALL be named in its output with the option to add.

#### Scenario: An adapter with no driver
- **GIVEN** a box with a USB Wi-Fi adapter the install recognises and no network interface for it
- **WHEN** the install runs without `--wifi-driver`
- **THEN** it says the adapter has no driver and that `--wifi-driver` installs one, and installs no driver

#### Scenario: The driver step in a dry run
- **GIVEN** the same box
- **WHEN** the install runs with `--wifi-driver --dry-run`
- **THEN** it prints the packages, the repository it would fetch and the DKMS commands, and changes nothing

### Requirement: The install sets the regulatory country

When the configuration it writes has no `wifi.country`, the install SHALL take it from
`--wifi-country`, else from the country the box's Wi-Fi is set to when that is not `00`, and
otherwise leave it out, saying that an access point will need it.

#### Scenario: Country from the option
- **GIVEN** a new install with `--wifi-country GB`
- **WHEN** the configuration is written
- **THEN** it carries `wifi.country` `GB`

### Requirement: The install keeps a factory copy of the configuration

When the install writes `/etc/wanpire/wanpire.json` it SHALL also write `/etc/wanpire/factory.json`,
the same document, readable by root only. On an installed box with no factory copy it SHALL
copy the configuration it finds and say so. The factory copy SHALL NOT be rewritten by a later
install that keeps the configuration. `uninstall --purge` SHALL remove it with `/etc/wanpire`.

#### Scenario: A first install
- **GIVEN** a box with `wlan0`, `eth0` and `eth1`
- **WHEN** the script runs with the roles
- **THEN** `/etc/wanpire/factory.json` holds the same document as `/etc/wanpire/wanpire.json`, in mode 0600

#### Scenario: A box installed before the copy existed
- **GIVEN** a box with a configuration and no factory copy
- **WHEN** the script runs again
- **THEN** it writes the factory copy from the configuration it finds, says so, and changes nothing else

#### Scenario: The roles changed since the install
- **GIVEN** a box whose configuration was changed from the page after the install
- **WHEN** the script runs again
- **THEN** the factory copy is unchanged
