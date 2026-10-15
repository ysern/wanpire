## ADDED Requirements

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
