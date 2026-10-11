## MODIFIED Requirements

### Requirement: A mapping fits the adapters and the mode

Every named adapter SHALL exist. In bridge mode, inbound and outbound SHALL be wired adapters or
Wi-Fi adapters run as access points, and control SHALL NOT be one of the bridge's ports. A Wi-Fi
adapter in the inbound or the outbound role SHALL be run as an access point, so its radio SHALL
support access-point mode. A Wi-Fi inbound adapter SHALL be refused in router mode, where
inbound is a client of the wider network.

#### Scenario: A missing adapter
- **GIVEN** a configuration naming outbound `eth9`, which the box does not have
- **WHEN** it is loaded
- **THEN** it is refused with a message naming `eth9` and listing the adapters the box has

#### Scenario: A Wi-Fi access point as a bridge port
- **GIVEN** a configuration in bridge mode with inbound `eth0` and outbound `[wlan1]`, a Wi-Fi adapter whose radio supports access-point mode, and an access point for `wlan1`
- **WHEN** it is loaded
- **THEN** it is accepted, and `wlan1` is an access point

#### Scenario: A radio that cannot be an access point
- **GIVEN** a configuration with outbound `[wlan1]`, a Wi-Fi adapter whose radio does not support access-point mode
- **WHEN** it is loaded
- **THEN** it is refused with a message saying `wlan1` cannot be an access point

#### Scenario: Wi-Fi inbound in router mode
- **GIVEN** a configuration in router mode with inbound `wlan1`, a Wi-Fi adapter
- **WHEN** it is loaded
- **THEN** it is refused with a message saying a Wi-Fi inbound adapter is an access point and works in bridge mode only

#### Scenario: Control on a bridge port
- **GIVEN** a configuration in bridge mode with control and inbound both `eth0`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying control cannot be a bridge port in bridge mode

## ADDED Requirements

### Requirement: An access point has a name, a password and a country

The configuration SHALL name, for every Wi-Fi adapter in the inbound or the outbound role, an
access point in `access_points` with an `ssid` of 1 to 32 bytes in UTF-8 and a `passphrase` of 8
to 63 printable ASCII characters, and SHALL carry a regulatory country in `wifi.country`: two
capital letters, an ISO 3166-1 country code, not `00`. A configuration with no Wi-Fi adapter in a
role SHALL need none of them. The control adapter SHALL NOT be an access point.

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
- **GIVEN** a configuration in bridge mode with inbound `eth0` and outbound `[eth1]` and no `access_points` or `wifi`
- **WHEN** it is loaded
- **THEN** it is accepted as before

### Requirement: The roles can be written back

wanpire SHALL write a configuration it has validated back to its file, keeping its control
adapter, its mode and its router settings, readable and writable by root only, replacing the
file in one step so that a reader never sees half of it.

#### Scenario: New roles written
- **GIVEN** a configuration with control `wlan0`, inbound `eth0` and outbound `[eth1]`
- **WHEN** the outbound adapter is changed to `wlan1` with its access point, and written
- **THEN** the file loads with control `wlan0`, inbound `eth0`, outbound `[wlan1]` and that access point, and only its owner may read it
