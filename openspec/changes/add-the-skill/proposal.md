## Why

The MCP gives an agent the tools; it does not teach manners. An agent that applies a link and
then stops to ask its user a question holds the only link for as long as the answer takes, and
one that polls too slowly loses its lease mid-test. The design (D7, D8) asks for a skill that
teaches an agent to use wanpire politely, in a format any agent host can load.

## What Changes

- **`skills/wanpire/SKILL.md`** in the open Agent Skills format (a folder with a `SKILL.md`,
  YAML front matter with `name` and `description`, then instructions). It teaches an agent to:
  - register the MCP (either way: the box's `/mcp`, or `wanpire mcp` over stdio);
  - ask for the link with who it is and why, and wait while queued: poll at the interval the
    answer gives (a third of the TTL), and say once that it is waiting;
  - describe a link by two endpoints and channels, preview it, then apply;
  - verify with the counters that the link is what it asked for;
  - clear and release the moment it is done, and before it ends its turn to wait for a person;
  - never end another agent's lease.
- **A test** that the skill is well formed and names only tools the MCP server has.

## Decided and assumed

Decided by the design (D7, D8) and A11: the skill lives at `skills/wanpire/SKILL.md`. Assumed
here (also in `docs/open-questions.md`): the skill carries no scripts, only instructions; it
assumes the MCP is registered as `wanpire`, and says how to register it when it is not.

## Capabilities

### New Capabilities

- `agent-skill`: the skill's format and what it teaches.

### Modified Capabilities

None.

## Impact

- New `skills/wanpire/SKILL.md`, `tests/unit/test_skill.py`. No code changes.
