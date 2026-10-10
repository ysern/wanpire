"""wanpire's MCP server: a thin layer of tools over the REST API.

Every tool calls ``/api/v1`` over HTTP with the box's token, so the token check and the broker
are the REST API's. On the box the HTTP client's transport is the app itself (no socket); on a
host (``wanpire mcp --url ...``) it is the network.

The agent carries its lease's ticket: ``wanpire_lease`` returns it and every change takes it.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__

INSTRUCTIONS = """\
wanpire makes a network line behave like a long internet link (delay, jitter, loss, bandwidth),
one client at a time. To change the link: wanpire_lease (who you are, why) -> if queued, say once
that you are waiting and call wanpire_poll every poll_every_s seconds until you hold it ->
wanpire_describe two ends ('london', 'los-angeles:mobile-4g'; see wanpire_endpoints) ->
wanpire_apply with your ticket -> check wanpire_counters -> wanpire_clear and wanpire_release
the moment you are done, and before you stop to wait for a person. While you hold the link,
call wanpire_poll at least every poll_every_s seconds or the lease (and the link) ends. Never
try to end another client's lease; reading needs no lease."""

logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per call is noise here

_MEANING = {
    400: "Not understood",
    401: "The box refused the token",
    404: "Unknown ticket (it expired from the queue, or was never issued); ask again with "
         "wanpire_lease",
    409: "You do not hold the link; wait for it with wanpire_poll",
    410: "Your lease ended; ask again with wanpire_lease if you still need the link",
    422: "Invalid request",
    500: "The box failed to change the link",
}


def rest_client(url: str, token: str, transport: httpx.AsyncBaseTransport | None = None,
                timeout_s: float = 30.0) -> httpx.AsyncClient:
    """An HTTP client for the box's REST API at ``url``, carrying the token."""
    return httpx.AsyncClient(base_url=url.rstrip("/") + "/api/v1", transport=transport,
                             headers={"Authorization": f"Bearer {token}"}, timeout=timeout_s)


def _ticket(ticket: str) -> dict[str, Any]:
    return {"X-Wanpire-Ticket": ticket}


async def _call(rest: httpx.AsyncClient, method: str, path: str, *, body: Any = None,
                headers: dict | None = None) -> Any:
    try:
        r = await rest.request(method, path, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise ToolError(f"Cannot reach the box: {e}") from e
    if r.status_code == 204:
        return None
    try:
        payload = r.json()
    except ValueError:
        payload = {"error": r.text}
    if r.is_success:
        return payload
    sentence = payload.get("error") if isinstance(payload, dict) else None
    meaning = _MEANING.get(r.status_code, f"The box answered {r.status_code}")
    raise ToolError(f"{meaning}: {sentence or r.reason_phrase}")


async def _lease_answer(rest: httpx.AsyncClient, a: dict) -> dict[str, Any]:
    status = await _call(rest, "GET", "status")
    ttl = status["broker"]["lease_ttl_s"] if a["holds"] else status["broker"]["queue_ttl_s"]
    every = max(1, int(ttl // 3))
    if a["holds"]:
        nxt = (f"You hold the link. Describe and apply it; call wanpire_poll every {every} s "
               "while you use it; clear and release it the moment you are done.")
    else:
        nxt = (f"Queued at position {a['position']}. Say once that you are waiting for the "
               f"link, then call wanpire_poll every {every} s until you hold it.")
    return {**a, "poll_every_s": every, "next": nxt}


def make_mcp(rest: httpx.AsyncClient) -> MCPServer:
    """The MCP server, its tools calling the REST API through ``rest``."""
    mcp = MCPServer(name="wanpire", version=__version__, instructions=INSTRUCTIONS)

    @mcp.tool()
    async def wanpire_status() -> dict[str, Any]:
        """The box at a glance: its mode, whether a link is applied and its counters, who
        holds the link, for what and since when, and who is queued. Needs no lease."""
        return await _call(rest, "GET", "status")

    @mcp.tool()
    async def wanpire_endpoints() -> dict[str, Any]:
        """The places a link can be described by, each with its channels (generic, fibre,
        cable, dsl, 4G, 5G, satellite...) and its default channel. Needs no lease."""
        return {"endpoints": await _call(rest, "GET", "endpoints")}

    @mcp.tool()
    async def wanpire_lease(who: str, purpose: str) -> dict[str, Any]:
        """Ask for the link. `who`: a name that tells you apart (e.g. your agent's name);
        `purpose`: what you are testing, shown to everyone. Returns your ticket, whether you
        hold the link or your place in the queue, and how often to poll."""
        a = await _call(rest, "POST", "lease", body={"who": who, "purpose": purpose})
        return await _lease_answer(rest, a)

    @mcp.tool()
    async def wanpire_poll(ticket: str) -> dict[str, Any]:
        """Keep your ticket alive and see where it stands: call it every poll_every_s seconds
        while queued and while you hold the link (it also keeps your link from being cleared
        by the box's dead-man timer)."""
        a = await _call(rest, "POST", "lease/poll", headers=_ticket(ticket))
        return await _lease_answer(rest, a)

    @mcp.tool()
    async def wanpire_describe(near: str, far: str) -> dict[str, Any]:
        """Work out a link from its two ends without changing anything. `near` is where the
        device under test is, `far` the rest of the network; each is
        `<endpoint>[:<channel>]`, e.g. 'london' or 'los-angeles:mobile-4g'. Returns the link
        each way (down = towards the device) and how it was worked out."""
        return await _call(rest, "POST", "preview", body={"near": near, "far": far})

    @mcp.tool()
    async def wanpire_apply(ticket: str, near: str | None = None, far: str | None = None,
                            down: dict | None = None, up: dict | None = None) -> dict[str, Any]:
        """Apply a link; needs the lease. Either two ends (`near`, `far`, as in
        wanpire_describe) or raw figures for `down` and `up`, each a dict of delay_ms,
        jitter_ms, loss_pct, burst_loss_pct, burst_length, rate_mbit, queue_ms,
        duplicate_pct, reorder_pct. Returns the link applied."""
        if near or far:
            body: dict = {"near": near, "far": far}
            if down or up:
                raise ToolError("Give either two ends (near, far) or figures (down, up), "
                                "not both")
        elif down is not None or up is not None:
            body = {k: v for k, v in (("down", down), ("up", up)) if v is not None}
        else:
            raise ToolError("Give two ends (near, far) or figures (down, up)")
        return await _call(rest, "PUT", "link", body=body, headers=_ticket(ticket))

    @mcp.tool()
    async def wanpire_clear(ticket: str) -> dict[str, Any]:
        """Take every impairment off the link; needs the lease."""
        await _call(rest, "DELETE", "link", headers=_ticket(ticket))
        return {"cleared": True}

    @mcp.tool()
    async def wanpire_counters() -> dict[str, Any]:
        """Per direction (down = towards the device), whether a link is applied and its
        counters: packets, bytes, packets wanpire dropped, packets the bandwidth's queue
        dropped (shaper_dropped), packets queued now. Needs no lease."""
        return await _call(rest, "GET", "link")

    @mcp.tool()
    async def wanpire_release(ticket: str) -> dict[str, Any]:
        """Give the link back (it is cleared for the next client), or leave the queue. Do it
        the moment you are done, and before you stop to wait for a person."""
        await _call(rest, "DELETE", "lease", headers=_ticket(ticket))
        return {"released": True}

    return mcp
