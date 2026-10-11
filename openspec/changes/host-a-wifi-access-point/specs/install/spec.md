## ADDED Requirements

### Requirement: A Wi-Fi adapter's driver is an optional step

The install SHALL install `hostapd` with the box's other packages. When asked with
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
