## Purpose

A skill, in the open Agent Skills format, that teaches an agent to drive wanpire through its MCP
politely: one link, shared, never held longer than needed.

## ADDED Requirements

### Requirement: The skill is a valid Agent Skill

`skills/wanpire/SKILL.md` SHALL start with YAML front matter whose `name` is `wanpire` (the
folder's name: lowercase letters, digits and hyphens, at most 64 characters) and whose
`description` (at most 1,024 characters) says what the skill does and when to use it. Its body
SHALL stay under 500 lines.

#### Scenario: Loaded by a host
- **GIVEN** the skill's folder copied into an agent host's skills
- **WHEN** the host reads its front matter
- **THEN** it finds the name `wanpire` and a description that names emulating a long or poor
  network link

### Requirement: The skill names only tools the MCP has

Every `wanpire_*` tool the skill names SHALL be a tool of the MCP server, and the skill SHALL
name every tool an agent needs to lease, wait, describe, apply, verify, clear and release.

#### Scenario: A tool renamed
- **GIVEN** a tool renamed in the MCP server
- **WHEN** the tests run
- **THEN** the skill's test fails until the skill names the new tool

### Requirement: The skill teaches the lease's manners

The skill SHALL tell the agent to: register the MCP if it is not; ask for the link with who it
is and its purpose; while queued, say once that it waits and poll at the interval the answer
gives; describe the link by two endpoints and channels and check the description before
applying; verify with the counters; clear and release as soon as it is done and before it ends
its turn to wait for a person; and never end another client's lease.

#### Scenario: Before asking the user something
- **GIVEN** an agent following the skill holds the link
- **WHEN** it needs to ask its user a question and end its turn
- **THEN** it clears the link and releases the lease first, and asks for it again afterwards
