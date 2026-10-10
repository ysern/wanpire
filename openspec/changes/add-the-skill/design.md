## Context

The MCP server (`add-the-mcp-server`) has nine tools and answers that say what to do next. The
skill adds what an answer cannot: when to give the link back, how to wait without nagging, and
what never to do.

## Goals / Non-Goals

**Goals:** one `SKILL.md`, short, that any host following the open Agent Skills format can load;
a test that keeps it in step with the MCP.

**Non-Goals:** scripts or references (the tools do the work); host-specific stubs (a host copies
the folder and adds what it needs).

## Decisions

### K1. One file, in the format's plain form

Front matter with `name`, `description`, `license` and `compatibility` (it needs the wanpire MCP
and network access to the box). The body: when to use it, registering the MCP, the lease's
life (ask, wait, use, give back), describing a link, verifying, troubleshooting by error, and
the rules. Under 200 lines, so an agent reads it whole.

Not taken: splitting into references (nothing is long enough to need it); a script that wraps
the polling (an agent polls through the MCP; a script would bypass it).

### K2. Waiting is a loop the agent runs, said once

The agent says once that it is waiting and for whom, then polls at `poll_every_s`. Between polls
it does work that does not need the link. If its host cannot wait (no sleep tool), it tells its
user it is queued and stops, after releasing its place, rather than holding a queue position it
will not poll.

### K3. Giving back is the default

The skill's rule is "hold the link only while traffic is flowing through it for you": clear and
release when done, before asking the user anything, and on any error that ends the test. Leasing
again later costs one call.

### K4. A test keeps it honest

`tests/unit/test_skill.py` parses the front matter, checks the format's limits, and checks that
the `wanpire_*` names in the body are exactly tools the MCP server lists, and that every tool a
lease's life needs is mentioned.

## Risks / Trade-offs

- **Hosts differ in how they load skills.** → The format's minimum only; the README says where
  common hosts look for skills.
