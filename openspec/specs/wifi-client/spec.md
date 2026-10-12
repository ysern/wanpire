# wifi-client Specification

## Purpose
Lets the box reach the wider network over Wi-Fi: a Wi-Fi inbound adapter joins a network as a
client, in router mode, and the line's traffic leaves through it.

## Requirements

### Requirement: A Wi-Fi inbound adapter joins its network in router mode

When router mode is set up with a Wi-Fi inbound adapter, wanpire SHALL join that adapter to the
configured network through `wpa_supplicant` run for that adapter only (WPA2-Personal and
WPA3-Personal accepted, or an open network with no password), take an IPv4 address for it by
DHCP, and route the traffic that comes in on outbound out through it, by a routing table and a
rule of the line's own. The settings SHALL be written to a file in the state directory, readable
by root only. A network not joined, or no address or gateway from it, SHALL fail the set-up with
the reason.

#### Scenario: Router mode with a Wi-Fi inbound
- **GIVEN** router mode with inbound `wlan1` joining `upstream` and outbound `eth1`
- **WHEN** the mode is set up
- **THEN** `wpa_supplicant` runs on `wlan1` for `upstream`, `wlan1` has an address from it, and what comes in on `eth1` is routed out through `wlan1`

#### Scenario: A wrong password
- **GIVEN** a network to join whose password the network refuses
- **WHEN** the mode is set up
- **THEN** the set-up fails with a message saying `wlan1` did not join the network, carrying `wpa_supplicant`'s last lines

#### Scenario: A name that is not plain text
- **GIVEN** a network to join whose name holds a quote and a closing brace
- **WHEN** its settings are written
- **THEN** the name is written in hexadecimal, so nothing in it is read as another setting

### Requirement: The box's own traffic stays on the control adapter

Joining a network SHALL NOT move the box's own traffic off the control adapter: the client's
default route SHALL have a metric above the box's own, the client SHALL answer ARP only for its
own addresses, it SHALL have no IPv6, and no hook SHALL change the box's name servers. Joining
and leaving SHALL NOT change the control adapter, its addresses, its Wi-Fi association or the
services that manage it.

#### Scenario: Control on the built-in Wi-Fi, on the same network
- **GIVEN** control `wlan0`, the built-in Wi-Fi joined to the owner's network, and inbound `wlan1` joining the same network
- **WHEN** `wlan1` joins and leaves
- **THEN** every command run names `wlan1`, the outbound adapter or the line's routing table, never `wlan0`

### Requirement: The network is left with the mode

Taking the mode down SHALL leave the network the inbound adapter joined, release its address and
remove the line's routing rule and table. Taking it down twice SHALL be safe. An inbound adapter
wanpire did not join SHALL be left alone.

#### Scenario: Down twice
- **GIVEN** router mode set up with `wlan1` joined to `upstream`
- **WHEN** the mode is taken down twice
- **THEN** `wpa_supplicant` no longer runs on `wlan1`, its settings file is gone, the line's rule is gone, and the second time changes nothing

#### Scenario: A wired inbound
- **GIVEN** router mode with a wired inbound `eth0`, whose address the system's own DHCP client keeps
- **WHEN** the mode is taken down
- **THEN** wanpire runs no DHCP client command on `eth0`
