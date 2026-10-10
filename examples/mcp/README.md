# Registering wanpire with an MCP host

Two ways, the same tools. Replace `<pi-address>` with the box's control address. The host signs
in with the box's account, the user name and the password made on the first visit to its web
page.

- **On the box (the default), streamable HTTP:** [`http.json`](http.json). Nothing to install on
  the host. The account travels in an `Authorization: Basic` header; put the base64 of
  `user:password` in `WANPIRE_BASIC`:

  ```sh
  export WANPIRE_BASIC=$(printf '%s' 'admin:<password>' | base64)
  ```

- **On the host, over stdio:** [`stdio.json`](stdio.json). Needs wanpire installed on the host
  (`pip install wanpire` from a checkout: `pip install .`); `wanpire mcp` then calls the box's
  REST API itself, with the user name in `WANPIRE_USER` and the password in `WANPIRE_PASSWORD`
  (or in a file named by `--password-file`). Use it when the host cannot send headers to a
  remote MCP server.

Hosts differ in how they expand `${...}`; where one does not, put the value itself in your own
copy of the file, and keep that copy private: it is the password people sign in with too.

From a command line, for hosts that have one (Claude Code shown):

```sh
claude mcp add --transport http wanpire http://<pi-address>:8080/mcp \
  --header "Authorization: Basic $WANPIRE_BASIC"
```

When the password changes (in the web page's Settings, or with `sudo wanpire account set
<user>` on the box over SSH), give the host the new one.

The skill in [`skills/wanpire/`](../../skills/wanpire/SKILL.md) teaches an agent how to use the
tools politely: lease, wait, apply, check, clear and release.
