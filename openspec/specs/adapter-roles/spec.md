# adapter-roles Specification

## Purpose
Says which adapter does what, so that the line can be impaired without ever touching the
channel wanpire is controlled through.

## Requirements

### Requirement: The main configuration maps adapters to roles

The main configuration SHALL be a JSON document with `schema` `wanpire-config/1`, a `mode`
(`bridge` or `router`), and `adapters` naming one `control` adapter, one `inbound` adapter and a
list of `outbound` adapters. While several links at once are not built, the list SHALL hold
exactly one adapter.

#### Scenario: A valid configuration
- **GIVEN** a configuration in bridge mode with control `wlan0`, inbound `eth0` and outbound `[eth1]`, all three present
- **WHEN** it is loaded
- **THEN** it is accepted with those roles

#### Scenario: Two outbound adapters
- **GIVEN** a configuration whose outbound list holds two adapters
- **WHEN** it is loaded
- **THEN** it is refused with a message saying one outbound adapter is supported for now

### Requirement: Outbound never shares its adapter

The outbound adapter SHALL NOT also be the control or the inbound adapter. Control and inbound
MAY share one. A mapping that breaks this SHALL be refused with a message that says why.

#### Scenario: Outbound is also control
- **GIVEN** a configuration with control `eth1` and outbound `[eth1]`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying outbound shares its adapter with nothing, because every impairment lives on it

#### Scenario: Control and inbound shared
- **GIVEN** a configuration in router mode with control and inbound both `eth0` and outbound `[eth1]`
- **WHEN** it is loaded
- **THEN** it is accepted

### Requirement: A mapping fits the adapters and the mode

Every named adapter SHALL exist. A Wi-Fi adapter's role SHALL depend on its side: a Wi-Fi
outbound adapter SHALL be run as an access point, in either mode, so its radio SHALL support
access-point mode; a Wi-Fi inbound adapter SHALL join a network as a client, in router mode only,
since a Wi-Fi client cannot be a bridge port. In bridge mode, inbound SHALL be a wired adapter,
outbound a wired adapter or a Wi-Fi access point, and control SHALL NOT be one of the bridge's
ports.

#### Scenario: A missing adapter
- **GIVEN** a configuration naming outbound `eth9`, which the box does not have
- **WHEN** it is loaded
- **THEN** it is refused with a message naming `eth9` and listing the adapters the box has

#### Scenario: A Wi-Fi access point as a bridge port
- **GIVEN** a configuration in bridge mode with inbound `eth0` and outbound `[wlan1]`, a Wi-Fi adapter whose radio supports access-point mode, and an access point for `wlan1`
- **WHEN** it is loaded
- **THEN** it is accepted, and `wlan1` is an access point

#### Scenario: A Wi-Fi access point in router mode
- **GIVEN** a configuration in router mode with inbound `eth0` and outbound `[wlan1]`, a Wi-Fi adapter, and an access point for it
- **WHEN** it is loaded
- **THEN** it is accepted, and `wlan1` is an access point

#### Scenario: A radio that cannot be an access point
- **GIVEN** a configuration with outbound `[wlan1]`, a Wi-Fi adapter whose radio does not support access-point mode
- **WHEN** it is loaded
- **THEN** it is refused with a message saying `wlan1` cannot be an access point

#### Scenario: A Wi-Fi inbound client in router mode
- **GIVEN** a configuration in router mode with inbound `wlan1`, a Wi-Fi adapter, outbound `[eth1]`, and a network for `wlan1` to join
- **WHEN** it is loaded
- **THEN** it is accepted, and `wlan1` is a client of that network, not an access point

#### Scenario: Wi-Fi as a bridge port
- **GIVEN** a configuration in bridge mode with inbound `wlan1`, a Wi-Fi adapter
- **WHEN** it is loaded
- **THEN** it is refused with a message saying a Wi-Fi client cannot be a bridge port, and to use router mode

#### Scenario: Control on a bridge port
- **GIVEN** a configuration in bridge mode with control and inbound both `eth0`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying control cannot be a bridge port in bridge mode

### Requirement: Every adapter is listed with its facts and role

The adapter list SHALL give, for every network adapter except loopback: its name, its kind
(`ethernet`, `usb-ethernet`, `wifi` or `virtual`), its hardware address, its link state, its
speed when known, whether it can be a Wi-Fi access point, and its role under the configuration.

#### Scenario: A box with a USB adapter
- **GIVEN** a box with an on-board port `eth0`, a USB Ethernet adapter `eth1` and Wi-Fi `wlan0` whose radio supports access-point mode
- **WHEN** the adapters are listed
- **THEN** `eth0` is `ethernet`, `eth1` is `usb-ethernet`, `wlan0` is `wifi` and can be an access point
- **AND** each carries its role from the configuration

### Requirement: An access point has a name, a password and a country

The configuration SHALL name, for a Wi-Fi outbound adapter, an access point in `access_points`
with an `ssid` of 1 to 32 bytes in UTF-8 and a `passphrase` of 8 to 63 printable ASCII
characters, and SHALL carry a regulatory country in `wifi.country`: two capital letters, an ISO
3166-1 country code, not `00`. A configuration with no Wi-Fi outbound adapter SHALL need none of
them. The control adapter SHALL NOT be an access point.

#### Scenario: A Wi-Fi outbound without its network
- **GIVEN** a configuration with outbound `[wlan1]`, a Wi-Fi adapter, and no access point for it
- **WHEN** it is loaded
- **THEN** it is refused with a message saying `wlan1` needs a network name and a password

#### Scenario: A password too short
- **GIVEN** an access point whose passphrase has 7 characters
- **WHEN** the configuration is loaded
- **THEN** it is refused with a message saying a password has 8 to 63 printable ASCII characters

#### Scenario: A name too long
- **GIVEN** an access point whose network name is 33 bytes long in UTF-8
- **WHEN** the configuration is loaded
- **THEN** it is refused with a message saying a network name has 1 to 32 bytes

#### Scenario: No country
- **GIVEN** a configuration with a Wi-Fi outbound adapter and its access point, and no `wifi.country`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying an access point needs the regulatory country

#### Scenario: A wired configuration as before
- **GIVEN** a configuration in bridge mode with inbound `eth0` and outbound `[eth1]` and no `access_points`, `wifi_clients` or `wifi`
- **WHEN** it is loaded
- **THEN** it is accepted as before

### Requirement: A Wi-Fi inbound client has the network to join

The configuration SHALL name, for a Wi-Fi inbound adapter, the network it joins in
`wifi_clients`: an `ssid` of 1 to 32 bytes in UTF-8 and a `passphrase` that is 8 to 63 printable
ASCII characters (WPA2 or WPA3-Personal), 64 hexadecimal digits (a WPA2 key), or empty (an open
network). An access point named for that adapter SHALL NOT stand in for it. The control adapter
SHALL NOT be joined to a network by wanpire.

#### Scenario: A Wi-Fi inbound without its network
- **GIVEN** a configuration in router mode with inbound `wlan1`, a Wi-Fi adapter, and no network for it in `wifi_clients`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying `wlan1` needs the network to join

#### Scenario: An open network
- **GIVEN** a network to join with the name `upstream` and an empty password
- **WHEN** the configuration is loaded
- **THEN** it is accepted

#### Scenario: A client password outside the rules
- **GIVEN** a network to join whose password has 7 characters
- **WHEN** the configuration is loaded
- **THEN** it is refused with a message saying a password has 8 to 63 printable ASCII characters, or 64 hexadecimal digits, or is empty for an open network

### Requirement: The roles can be written back

wanpire SHALL write a configuration it has validated back to its file, keeping its control
adapter, its mode and its router settings, readable and writable by root only, replacing the
file in one step so that a reader never sees half of it.

#### Scenario: New roles written
- **GIVEN** a configuration with control `wlan0`, inbound `eth0` and outbound `[eth1]`
- **WHEN** the outbound adapter is changed to `wlan1` with its access point, and written
- **THEN** the file loads with control `wlan0`, inbound `eth0`, outbound `[wlan1]` and that access point, and only its owner may read it

### Requirement: A configuration names its missing line adapters

A configuration loaded without the adapter check SHALL be able to say which of its line adapters
(inbound and outbound) the box does not have now, so that the box can start with the line down
and say why. The control adapter SHALL NOT be among them: without it the box cannot be reached,
and its absence is refused as before.

#### Scenario: The outbound adapter is unplugged
- **GIVEN** a configuration with control `wlan0`, inbound `eth0` and outbound `[wlx1]`, on a box that has `wlan0` and `eth0`
- **WHEN** it is loaded without the adapter check and asked for its missing adapters
- **THEN** it names `wlx1` as the outbound adapter that is not plugged in

#### Scenario: Everything plugged in
- **GIVEN** the same configuration on a box that has `wlan0`, `eth0` and `wlx1`
- **WHEN** it is asked for its missing adapters
- **THEN** there are none
