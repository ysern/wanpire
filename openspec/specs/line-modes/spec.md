# line-modes Specification

## Purpose
Puts the box on the line in one of two ways, and takes it off again leaving the box as it was.

## Requirements

### Requirement: Bridge mode joins inbound and outbound transparently

In bridge mode, setting up SHALL join inbound and outbound in a bridge with STP off, with no
address on the bridge or its ports, all up. A device behind outbound SHALL reach the network
beyond inbound on the same subnet, as if the box were a cable. A port that carries an IP address
SHALL be refused, and its address left alone.

#### Scenario: A device reaches the other side
- **GIVEN** a device behind outbound and a host beyond inbound, on one subnet
- **WHEN** bridge mode is set up
- **THEN** the device pings the host, and the box has no address on the bridge or its ports

#### Scenario: A port with an address
- **GIVEN** an inbound adapter that carries an IPv4 address
- **WHEN** bridge mode is set up
- **THEN** it is refused with a message naming the adapter and its address
- **AND** the address is still there

#### Scenario: Torn down
- **GIVEN** bridge mode set up
- **WHEN** it is torn down
- **THEN** the bridge no longer exists and the device no longer reaches the host

### Requirement: Router mode gives the device a network of its own behind NAT

In router mode, setting up SHALL give outbound an address on a private network of its own,
serve DHCP on it, forward between outbound and inbound, and masquerade what leaves through
inbound. Its firewall rules SHALL live in an nftables table of wanpire's own.

#### Scenario: A device gets an address and reaches the far side through NAT
- **GIVEN** a device behind outbound with no address, and a host beyond inbound
- **WHEN** router mode is set up and the device asks for an address by DHCP
- **THEN** it gets one in the router's network, and reaches the host
- **AND** the host sees the box's inbound address as the source, not the device's

### Requirement: Tearing a mode down leaves the box as it was

Tearing down SHALL remove everything setting up added (bridge, address, DHCP server, nftables
table) and SHALL put IPv4 forwarding back to the value it had before setting up. Setting up
and tearing down SHALL each be safe to run twice.

#### Scenario: Forwarding restored
- **GIVEN** a box with IPv4 forwarding off
- **WHEN** router mode is set up and torn down
- **THEN** forwarding is off, outbound has no address, no DHCP server runs, and wanpire's nftables table is gone

#### Scenario: Twice
- **WHEN** a mode is set up twice and torn down twice
- **THEN** neither second call fails, and the box ends as it started
