## ADDED Requirements

### Requirement: The box can be reset to its install state

`wanpire factory-reset` on the box SHALL restore `/etc/wanpire/wanpire.json` from the factory
copy, remove the account, and restart the unit when one runs, else tear the mode down and set it
up again with the restored roles; it SHALL ask for a "yes" at a terminal unless `--yes` is given,
and SHALL refuse with a message saying to run the install again when there is no factory copy.
`POST /api/v1/factory-reset` with `{"confirm": "reset"}` SHALL need the account, SHALL be refused
422 without that word and 409 while a lease is held, and SHALL otherwise answer 202 and then
perform the same reset and restart the server, so that the next request finds a box with no
account. The MCP SHALL NOT offer it.

#### Scenario: Reset on the box
- **GIVEN** a box with an account, roles changed from the page, and a factory copy
- **WHEN** `sudo wanpire factory-reset --yes` is run
- **THEN** the configuration equals the factory copy, no account exists, and the unit is restarted

#### Scenario: No factory copy
- **GIVEN** a box installed before the factory copy existed
- **WHEN** `sudo wanpire factory-reset --yes` is run
- **THEN** it refuses, saying to run the install again, and changes nothing

#### Scenario: Reset from the API
- **GIVEN** a signed-in client, no lease held
- **WHEN** it posts `{"confirm": "reset"}` to `/api/v1/factory-reset`
- **THEN** the answer is 202, and the next `GET /api/v1/setup` says an account is needed

#### Scenario: A lease is held
- **GIVEN** an agent holds the lease
- **WHEN** a client posts the reset
- **THEN** the answer is 409 naming the holder, and nothing changes

#### Scenario: The word is missing
- **WHEN** a client posts `{}` or `{"confirm": "yes"}`
- **THEN** the answer is 422 saying the word `reset` is needed, and nothing changes
