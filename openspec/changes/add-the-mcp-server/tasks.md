## 1. Tests first

- [ ] 1.1 Failing tests, in process: the tools listed; status; endpoints; describe leaves the engine alone
- [ ] 1.2 Failing tests: lease, queued with poll_every_s, poll granted, release; the same broker as REST
- [ ] 1.3 Failing tests: apply from ends and from figures, clear, counters; errors (ended with reason, not the holder, invalid)
- [ ] 1.4 Failing tests: `/mcp` without the token 401; an MCP client over real HTTP with the token
- [ ] 1.5 Failing tests: `wanpire mcp` without a token refuses; with one, a stdio client calls status

## 2. Build

- [ ] 2.1 `mcp_server.py` until green
- [ ] 2.2 `/mcp` in `api.py`; `wanpire mcp` in `cli.py`
- [ ] 2.3 `examples/mcp/` client configurations

## 3. Close

- [ ] 3.1 On the Pi against a namespace bed: an MCP client over HTTP leases, applies, reads the counters, releases
- [ ] 3.2 Journal, open questions, README
