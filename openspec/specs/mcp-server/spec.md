# mcp-server Specification

## Purpose
An MCP server through which any MCP host drives wanpire, as a thin layer over its REST API.

## Requirements

### Requirement: The tools are a thin layer over the REST API

The MCP server SHALL offer the tools `wanpire_status`, `wanpire_endpoints`, `wanpire_lease`,
`wanpire_poll`, `wanpire_describe`, `wanpire_apply`, `wanpire_clear`, `wanpire_counters` and
`wanpire_release`, and each SHALL do its work by calling the REST API under `/api/v1` with the
box's account. No tool SHALL end another client's lease.

#### Scenario: The tools listed
- **GIVEN** an MCP client connected to the server
- **WHEN** it lists the tools
- **THEN** it sees those nine, and none that ends another client's lease

#### Scenario: The same broker
- **GIVEN** a person holds the link through the web page
- **WHEN** an agent calls `wanpire_lease`
- **THEN** the agent is queued at position 1, as a REST client would be

### Requirement: Leasing and waiting through tools

`wanpire_lease` SHALL take who is asking and why, and SHALL return the ticket, whether it holds
the link, its place in the queue and how often to poll (a third of the TTL). `wanpire_poll`
SHALL renew the ticket and say the same. `wanpire_release` SHALL give the lease back or leave the
queue.

#### Scenario: Queued, then granted
- **GIVEN** another client holds the link
- **WHEN** the agent calls `wanpire_lease`, the other client releases, and the agent calls
  `wanpire_poll`
- **THEN** the first answer says position 1 and how often to poll, and the second says it holds
  the link

### Requirement: A link described by two ends

`wanpire_describe` SHALL take two ends, `<endpoint>[:<channel>]`, and return the link both ways
and how it was worked out, changing nothing. `wanpire_apply` SHALL take the ticket and either two
ends or raw figures for `down` and `up`, and SHALL apply them through the REST API.

#### Scenario: Describe, then apply
- **GIVEN** the agent holds the link
- **WHEN** it describes `london` to `los-angeles:mobile-4g`, then applies the same ends
- **THEN** the description gives 98.8 ms each way, the engine was untouched by it, and the apply
  reaches the engine with that link

### Requirement: Errors say what to do next

A REST error SHALL become a tool error carrying the REST API's sentence; an ended lease SHALL say
that the lease ended and why; a change without the lease SHALL say who holds it.

#### Scenario: Ended by hand
- **GIVEN** the agent's lease was ended by hand with the reason "bench needed"
- **WHEN** the agent calls `wanpire_apply`
- **THEN** the tool fails with a message that says its lease ended and gives "bench needed"

### Requirement: Served on the box behind the account

`wanpire serve` SHALL serve the MCP over streamable HTTP at `/mcp`, and SHALL refuse a request
without the box's account, in HTTP Basic credentials, with 401.

#### Scenario: No credentials
- **GIVEN** the server running
- **WHEN** a client posts to `/mcp` without credentials
- **THEN** it is answered 401

#### Scenario: With the account, over HTTP
- **GIVEN** the server running
- **WHEN** an MCP client connects to `/mcp` with the account's user and password and calls `wanpire_status`
- **THEN** it gets the box's mode and broker

### Requirement: Runnable on a host over stdio

`wanpire mcp --url <box>` SHALL run the same tools over stdio, calling the box's REST API at that
URL with the account's user from `WANPIRE_USER` and its password from `WANPIRE_PASSWORD` or a
file named by `--password-file`, and SHALL refuse to start without both.

#### Scenario: No password
- **GIVEN** `WANPIRE_USER` set, and no `WANPIRE_PASSWORD` and no password file
- **WHEN** `wanpire mcp --url http://<pi-address>:8080` starts
- **THEN** it exits with a message saying where the user name and the password go
