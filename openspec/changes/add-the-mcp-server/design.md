## Context

D8 gives the server three faces; the REST API and the web page exist. This change adds the MCP,
for agents. The SDK is the official MCP Python SDK, 2.x (`mcp.server.mcpserver.MCPServer`).

## Goals / Non-Goals

**Goals:** the tools, served on the box at `/mcp` and on a host over stdio, a client
configuration, tests in process and over real HTTP.

**Non-Goals:** OAuth (one bearer token is the box's model); resources and prompts (the skill
carries the guidance); scenarios (the engine has none); a tool to end another's lease.

## Decisions

### M1. One factory, one REST client

`make_mcp(rest)` builds the `MCPServer` from an `httpx.AsyncClient` already pointed at the box
with the token. On the box that client's transport is `httpx.ASGITransport(app)`: real HTTP
requests through the app's own routes, token check and broker included, with no socket, so it
works whatever address the server listens on. Over stdio it is a plain client to the box's URL.

Not taken: tools calling the core directly (A9: two ways in that could disagree); a loopback
socket (the server listens on the control address only, not on 127.0.0.1).

### M2. The agent carries the ticket

`wanpire_lease` returns the ticket and every change takes it as an argument. The server keeps
nothing per MCP session, so streamable HTTP runs stateless with JSON responses, and a reconnect
loses nothing.

Not taken: a ticket kept per MCP session (stateful sessions; a host that reconnects would lose
its lease's ticket and wait for the TTL).

### M3. Answers that teach the next step

Each lease answer carries `poll_every_s` (a third of the TTL) and a one-line `next`: hold the
link and apply; or wait, say once that you wait, and poll. Errors are `ToolError`s with the REST
API's own sentence, prefixed by what it means: an ended lease, another holder, an invalid link.

Tools return `dict[str, Any]`, so the SDK sends structured content as well as the JSON text
(a bare `dict` or `list` return type gives text only, a list one block per item).

### M4. `/mcp` on the box, behind the token

The SDK's streamable HTTP handler is added as a route `/mcp` of the FastAPI app, wrapped in a
check of the same bearer token, before the web page's static mount; its session manager runs in
the app's lifespan. DNS-rebinding protection is off: it guards servers with no authentication
from a browser, and this one needs the token.

### M5. `wanpire mcp` on a host

`wanpire mcp --url http://<pi-address>:8080 [--token-file F]`, the token from `WANPIRE_TOKEN`
otherwise, runs the same server over stdio. The owner's question was whether this saves the
Pi's CPU; it does not measurably (the MCP is idle between calls), so the box stays the default
and stdio is for a host that cannot reach `/mcp` or wants the token in its own keyring.

### M6. The client configuration

`examples/mcp/http.json` (a URL and an `Authorization` header) and `examples/mcp/stdio.json` (the
`wanpire mcp` command), in the `mcpServers` shape most hosts read, with placeholders only.

## Risks / Trade-offs

- **The SDK's 2.x line is young** and renamed its server class from 1.x. → Pinned to `<3`; the
  layer is small enough to port.
- **The token sits in the host's MCP configuration.** → The examples read it from an
  environment variable where the host supports it.
