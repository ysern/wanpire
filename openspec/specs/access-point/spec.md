# access-point Specification

## Purpose
Lets a wireless device under test join wanpire itself: a Wi-Fi outbound adapter runs an access
point, so the device's traffic crosses the box and every impairment applies to it.

## Requirements

### Requirement: A Wi-Fi outbound adapter runs an access point

When the mode is set up, a Wi-Fi outbound adapter SHALL run an access point through `hostapd`: on 5 GHz, on channel 36 at 80 MHz, with the configured network
name and password, WPA2-Personal and WPA3-Personal both accepted, under the configured regulatory
country. In bridge mode the access point SHALL be a port of the bridge. In router mode the
access point SHALL carry the router's address and its DHCP server. The access point's
settings SHALL be written to a file in the state directory, readable by root only.

#### Scenario: Bridge mode with an access point
- **GIVEN** bridge mode with inbound `eth0` and outbound `wlan1`, an access point for it named `lab-ap`
- **WHEN** the mode is set up
- **THEN** `hostapd` runs on `wlan1` with network name `lab-ap`, channel 36, the country, WPA2 and WPA3, and `bridge=wpbr0`
- **AND** `eth0` is a port of the bridge

#### Scenario: Router mode with an access point
- **GIVEN** router mode with inbound `eth0` and outbound `wlan1`, an access point for it
- **WHEN** the mode is set up
- **THEN** `hostapd` runs on `wlan1` with no bridge, `wlan1` carries the router's address, and DHCP is served on it

#### Scenario: A name that is not plain text
- **GIVEN** an access point whose network name holds a quote and a non-ASCII letter
- **WHEN** its settings are written
- **THEN** the name is written in hexadecimal, so nothing in it is read as another setting

### Requirement: The access point is taken down with the mode

Taking the mode down SHALL stop every access point wanpire started for these adapters and
remove its settings file. Setting up or taking down twice SHALL be safe. An access point that
does not come up SHALL fail the set-up with `hostapd`'s reason.

#### Scenario: Down twice
- **GIVEN** bridge mode set up with an access point on `wlan1`
- **WHEN** the mode is taken down twice
- **THEN** `hostapd` no longer runs on `wlan1`, its settings file is gone, and the second time changes nothing

#### Scenario: hostapd refuses
- **GIVEN** an access point whose radio refuses the channel
- **WHEN** the mode is set up
- **THEN** the set-up fails with a message carrying the last lines `hostapd` printed

### Requirement: The control adapter is never touched

Running or stopping an access point SHALL NOT change the control adapter, its addresses, its
Wi-Fi association or the services that manage it.

#### Scenario: Control on the built-in Wi-Fi
- **GIVEN** control `wlan0`, the built-in Wi-Fi joined to the owner's network, and outbound `wlan1`, a USB Wi-Fi adapter
- **WHEN** the access point on `wlan1` is started and stopped
- **THEN** every command run names `wlan1` or the bridge, never `wlan0`
