# endpoint-presets Specification

## Purpose
Describes the ends of a link: a place and the ways of reaching the internet there, so that a
link can be asked for as *this place on this kind of connection to that place on that kind*.

## Requirements

### Requirement: An endpoint preset is a JSON file with a published schema

An endpoint preset SHALL be a JSON document with `schema` set to `wanpire-endpoint/1`, an `id`,
a `name`, a `location` (latitude, longitude, country code, world region), a `default_channel`
and at least one channel. A JSON Schema for it SHALL be published in the repository, and every
shipped preset SHALL validate against it.

#### Scenario: Every shipped preset matches the schema
- **WHEN** each shipped endpoint preset is checked against the published schema
- **THEN** every one is valid

#### Scenario: A preset with no channel is refused
- **GIVEN** a preset whose `channels` is empty
- **WHEN** it is loaded
- **THEN** it is refused with a message saying a preset needs at least one channel

### Requirement: Channels are generic kinds and carry their figures per direction

A channel SHALL have a `kind` from the list `generic`, `media-private-network`,
`enterprise-fibre`, `business-fibre`, `consumer-fibre`, `cable`, `dsl`, `fixed-wireless`,
`mobile-4g`, `mobile-5g`, `satellite-leo`, `satellite-geo`, a description, and `down` and `up`
figures as seen from the endpoint, using the link model's settings. A channel's figures SHALL
be the access link's contribution only, and SHALL name at least one source. Every preset SHALL
have a `generic` channel.

#### Scenario: Figures outside the link model's ranges are refused
- **GIVEN** a preset whose channel asks for 120% loss
- **WHEN** it is loaded
- **THEN** it is refused with a message naming the preset, the channel and `loss_pct`

#### Scenario: An unknown kind is refused
- **GIVEN** a channel of kind `carrier-x`
- **WHEN** the preset is loaded
- **THEN** it is refused with a message listing the known kinds

#### Scenario: A preset without a generic channel is refused
- **GIVEN** a preset whose only channel is `mobile-4g`
- **WHEN** it is loaded
- **THEN** it is refused with a message saying every preset has a `generic` channel

### Requirement: A channel is chosen per end, or the default

An end SHALL be named as `<endpoint>` or `<endpoint>:<channel>`, where `<endpoint>` is a
shipped preset's id or a path to a preset file. Without a channel, the preset's default
channel SHALL be used. An unknown endpoint or channel SHALL be refused with the ones known.

#### Scenario: The default channel
- **GIVEN** the London preset, whose default channel is `generic`
- **WHEN** the end `london` is resolved
- **THEN** the generic channel is used

#### Scenario: An unknown channel
- **WHEN** the end `london:carrier-pigeon` is resolved
- **THEN** it is refused with a message listing London's channels

#### Scenario: A preset from a file
- **GIVEN** a valid preset file written by a user outside the repository
- **WHEN** its path is given as an end
- **THEN** it is used like a shipped preset

### Requirement: A starter set ships, naming no provider

The repository SHALL ship presets for London, Los Angeles, New York, Vancouver, Sydney, Mumbai
and Tokyo. Their figures SHALL come only from sources whose licence allows redistribution, or
from wanpire's own estimates stated as such with their reasoning. No preset SHALL name a
network provider, carrier or vendor.

#### Scenario: The seven cities
- **WHEN** the shipped presets are listed
- **THEN** they include london, los-angeles, new-york, vancouver, sydney, mumbai and tokyo

#### Scenario: Every source is redistributable or our own
- **WHEN** the sources of every shipped channel are read
- **THEN** each one's licence is CC0-1.0, CC-BY-4.0 or MIT (wanpire's own estimate)
