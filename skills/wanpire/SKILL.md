---
name: wanpire
description: Make a network link behave like a long or poor internet connection (delay, jitter, loss, bandwidth) with a wanpire box, through its MCP tools, and share the box politely with other agents. Use when testing software over a distant, slow, lossy or mobile/satellite network link, e.g. "London to Sydney on 4G".
license: MIT
compatibility: Needs the wanpire MCP server (on the box at http://<box>:8080/mcp, or `wanpire mcp` over stdio) and network access to the box.
---

# wanpire

A wanpire box sits on an Ethernet line and makes it behave like a long internet link. There is
**one link and possibly many clients** (other agents, people at its web page), so a broker hands
out a **lease**: only the holder changes the link, a lease lives only while it is used, and the
link is cleared between holders.

Directions are seen from the device under test: **down** is towards it, **up** away from it.

## 1. Make sure the MCP is registered

Look for tools named `wanpire_*`. If there are none, register the MCP as `wanpire`, one of two
ways (the box's token is in `/etc/wanpire/token` on the box; ask your user for it and for the
box's address, never guess them):

- **On the box (preferred):** streamable HTTP at `http://<box>:8080/mcp`, with the header
  `Authorization: Bearer <token>`. Nothing to install.
- **On this machine, over stdio:** `wanpire mcp --url http://<box>:8080`, with the token in
  `WANPIRE_TOKEN`. Needs wanpire installed here.

Reading needs no lease: `wanpire_status` (mode, holder, queue, counters), `wanpire_endpoints`,
`wanpire_describe`, `wanpire_counters`.

## 2. Ask for the link

Call `wanpire_lease` with `who` (a name that tells you apart, e.g. your agent's name and task)
and `purpose` (what you are testing; everyone sees it). Keep the `ticket` it returns: every change
needs it.

- `holds: true`: the link is yours. Go to 3.
- `holds: false`: you are queued at `position`. **Say once** to your user that you are waiting
  for the link, and behind whom (`wanpire_status` shows the holder and its purpose). Then call
  `wanpire_poll` with your ticket every `poll_every_s` seconds until `holds` is true. Do not
  announce every poll. Between polls, do work that does not need the link.
- If you cannot wait (no way to sleep between calls, or your user would rather not), call
  `wanpire_release` to leave the queue and tell your user the link is busy. A place in the queue
  you will not poll only expires anyway.

**While you hold the link, keep polling** at `poll_every_s`. A lease without a call for its TTL
ends, and the box clears the link by itself: your test would silently run on a clean line.

## 3. Describe the link, then apply it

A link is two ends, each `<endpoint>[:<channel>]`:

- `near` is where the device under test is; `far` is the rest of the network.
- `wanpire_endpoints` lists the places (e.g. `london`, `los-angeles`, `sydney`, `tokyo`) and
  their channels (`generic`, `consumer-fibre`, `cable`, `dsl`, `mobile-4g`, `mobile-5g`,
  `satellite-leo`, `satellite-geo`, ...). No channel means the place's default.

First call `wanpire_describe` with `near` and `far`. It changes nothing and returns the link both
ways (delay, jitter, loss, bandwidth) and how it was worked out. Check it is what your test needs,
then call `wanpire_apply` with your ticket and the same ends.

For exact figures instead, call `wanpire_apply` with `down` and `up`, each a dict of `delay_ms`,
`jitter_ms`, `loss_pct`, `burst_loss_pct` with `burst_length`, `rate_mbit`, `queue_ms`,
`duplicate_pct`, `reorder_pct`; for example `{"delay_ms": 150, "loss_pct": 1}`.

## 4. Verify

Run your traffic, then call `wanpire_counters`. Each direction shows `applied`, `packets`,
`bytes`, `dropped` (wanpire's own loss), `shaper_dropped` (the bandwidth's queue overflowing) and
`queued`. Packets rising in the direction you expect is your proof that the traffic crosses the
link. If they stay at zero, your traffic does not go through the box: say so rather than
reporting results.

When you report results, give the link you applied (from `wanpire_describe`) and the counters.

## 5. Give it back

**Hold the link only while traffic is flowing through it for you.** Call `wanpire_clear` and then
`wanpire_release` with your ticket:

- the moment your test is done;
- **before you end your turn to wait for a person** (a question, an approval, a manual step),
  however short you expect the wait to be. Lease again afterwards: it costs one call;
- when a test fails and you stop.

## Errors

The tools' errors say what happened and what to do:

- *Your lease ended* (someone ended it by hand, with a reason, or it expired): stop the test,
  tell your user the reason, and ask with `wanpire_lease` again only if you still need the link.
- *You do not hold the link*: you are still queued; keep polling.
- *Unknown ticket*: your place expired; ask again.
- *Invalid request*: fix the ends or the figures (the message names the problem).
- *The box failed to change the link*: tell your user; do not retry in a loop.

## Rules

- **Never end another client's lease**, and never ask a person to do it for you to jump the
  queue. If you have waited long, tell your user who holds the link and for what.
- One ticket per task. Do not ask for the link twice in parallel.
- Never share the token in output, logs or commits.
