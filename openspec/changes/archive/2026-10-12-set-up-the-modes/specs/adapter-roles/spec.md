## Purpose

Says which adapter does what, so that the line can be impaired without ever touching the
channel wanpire is controlled through.

## ADDED Requirements

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

Every named adapter SHALL exist. In bridge mode, inbound and outbound SHALL be wired adapters,
and control SHALL NOT be one of the bridge's ports. A Wi-Fi outbound adapter SHALL be refused
until access-point mode is built.

#### Scenario: A missing adapter
- **GIVEN** a configuration naming outbound `eth9`, which the box does not have
- **WHEN** it is loaded
- **THEN** it is refused with a message naming `eth9` and listing the adapters the box has

#### Scenario: Wi-Fi as a bridge port
- **GIVEN** a configuration in bridge mode with inbound `wlan0`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying a Wi-Fi client cannot be a bridge port

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
