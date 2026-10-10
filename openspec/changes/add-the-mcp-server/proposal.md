## Why

wanpire is meant to be driven by AI agents as much as by people (D8). An agent host speaks MCP;
the box speaks REST. A thin MCP server lets any MCP host lease the link, describe it by two
places, apply it, check it and give it back, without learning the REST API, and with the same
broker deciding who drives.

## What Changes

- **An MCP server** (`src/wanpire/mcp_server.py`) on the official MCP Python SDK. Its tools are a
  thin layer over the REST API: `wanpire_status`, `wanpire_endpoints`, `wanpire_lease`,
  `wanpire_poll`, `wanpire_describe`, `wanpire_apply`, `wanpire_clear`, `wanpire_counters`,
  `wanpire_release`. Each calls `/api/v1` over HTTP, so the token check and the broker are the
  REST API's.
- **On the box, at `/mcp`**, served by `wanpire serve` over streamable HTTP, behind the same
  bearer token.
- **On any host, over stdio**: `wanpire mcp --url http://<pi-address>:8080`, the token from
  `WANPIRE_TOKEN` or a file, calling the box's REST API.
- **A client configuration** any MCP host can use, for both ways, in `examples/mcp/`.
- No tool ends another client's lease: that is a person's decision, at the web page.

## Decided and assumed

Decided by the design (D8, A9): the MCP is a thin layer over the REST API and calls it over HTTP;
it runs on the box by default and can run on a host over stdio. Assumed here (also in
`docs/open-questions.md`):

- the agent carries its ticket: `wanpire_lease` returns it, and every change takes it, so the
  server keeps no state per MCP session (streamable HTTP is stateless, JSON responses);
- on the box the tools reach the REST API in process through an HTTP transport bound to the app
  (no socket), so it works whatever address the server listens on;
- `/mcp` needs the box's bearer token in an `Authorization` header; the SDK's DNS-rebinding
  check is off, since the token already stops a browser that does not have it;
- the MCP SDK is pinned to its 2.x line.

## Capabilities

### New Capabilities

- `mcp-server`: the tools, their errors, the two ways of running it, the client configuration.

### Modified Capabilities

None.

## Impact

- New `src/wanpire/mcp_server.py`; `api.py` mounts `/mcp`; `cli.py` gains `mcp`.
- Runtime dependencies: `mcp>=2.3,<3`, `httpx`.
- New `examples/mcp/` (streamable HTTP and stdio client configurations).
