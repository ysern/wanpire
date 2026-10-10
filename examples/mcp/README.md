# Registering wanpire with an MCP host

Two ways, the same tools. Replace `<pi-address>` with the box's control address, and give the
host the box's token (`/etc/wanpire/token` on the box) in `WANPIRE_TOKEN`.

- **On the box (the default), streamable HTTP:** [`http.json`](http.json). Nothing to install on
  the host. The token travels in an `Authorization: Bearer` header.
- **On the host, over stdio:** [`stdio.json`](stdio.json). Needs wanpire installed on the host
  (`pip install wanpire` from a checkout: `pip install .`); `wanpire mcp` then calls the box's
  REST API itself. Use it when the host cannot send headers to a remote MCP server.

Hosts differ in how they expand `${WANPIRE_TOKEN}`; where one does not, put the token itself in
your own copy of the file, and keep that copy private.

From a command line, for hosts that have one (Claude Code shown):

```sh
claude mcp add --transport http wanpire http://<pi-address>:8080/mcp \
  --header "Authorization: Bearer $WANPIRE_TOKEN"
```

The skill in [`skills/wanpire/`](../../skills/wanpire/SKILL.md) teaches an agent how to use the
tools politely: lease, wait, apply, check, clear and release.
