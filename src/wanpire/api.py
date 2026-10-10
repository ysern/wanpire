"""wanpire's REST API: the engine's only interface. The web UI and the MCP are its clients.

Every route under ``/api/v1`` needs the box's bearer token. Changes to the link need the
broker's lease, shown by its ticket in ``X-Wanpire-Ticket``; reading needs no ticket.

    GET    /api/v1/status            mode, outbound adapter, link counters, holder and queue
    POST   /api/v1/lease             {"who", "purpose"} -> ticket, holds, position
    POST   /api/v1/lease/poll        keep the ticket alive (renews the dead-man for the holder)
    DELETE /api/v1/lease             release the lease, or leave the queue
    DELETE /api/v1/lease/holder      {"reason"}: end the current lease by hand
    GET    /api/v1/link              the link's counters
    PUT    /api/v1/link              {"down", "up"} or {"near", "far"}   (lease)
    DELETE /api/v1/link              clear                               (lease)
    GET    /api/v1/endpoints         the shipped endpoints and their channels
    GET    /api/v1/endpoints/{id}    one preset document
    POST   /api/v1/preview           {"near", "far"} -> the link and how it was worked out
    GET    /api/v1/adapters          every adapter, its facts and its role
    POST   /mcp                      the MCP (streamable HTTP), its tools calling the routes above

The web UI's static files are served at ``/`` without the token: they hold no data, and the
page itself calls the routes above with the token.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from . import catalogue
from .broker import Broker, LeaseEnded, NotHolder, UnknownTicket
from .config import Config, InvalidConfig
from .engine import CommandFailed, RefusedAdapter
from .model import InvalidLink, Link
from .presets import InvalidPreset

TICKET = "X-Wanpire-Ticket"
WEB = Path(__file__).parent / "web"


class _Status(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _mcp_http_handler(mcp):
    """The SDK's streamable HTTP handler for ``mcp``: stateless, JSON answers."""
    from mcp.server.transport_security import TransportSecuritySettings
    http = mcp.streamable_http_app(
        streamable_http_path="/mcp", stateless_http=True, json_response=True,
        # the bearer token stops a browser without it; the host check would only refuse
        # the box's own name and addresses
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    return next(r.endpoint for r in http.routes if getattr(r, "path", None) == "/mcp")


class _Guard:
    """An ASGI app: the box's bearer token, then the MCP's handler."""

    def __init__(self, token: str, handler: list):
        self._token = token.encode()
        self._handler = handler

    async def __call__(self, scope, receive, send):
        given = dict(scope.get("headers") or []).get(b"authorization", b"")
        scheme, _, value = given.partition(b" ")
        if scheme.lower() != b"bearer" or not secrets.compare_digest(value, self._token):
            await JSONResponse({"error": "a bearer token is needed"}, status_code=401)(
                scope, receive, send)
            return
        if not self._handler:
            await JSONResponse({"error": "the MCP is starting"}, status_code=503)(
                scope, receive, send)
            return
        await self._handler[0](scope, receive, send)


def create_app(engine, broker: Broker, config: Config, token: str, list_adapters,
               tick_s: float | None = 5.0, with_mcp: bool = True) -> FastAPI:
    if not token:
        raise ValueError("the API needs a token")
    outbound = config.outbound[0]

    mcp = None
    mcp_handler = []  # the MCP's HTTP handler, made afresh each time the app starts

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        task = None
        if tick_s:
            async def tick():
                while True:
                    await asyncio.sleep(tick_s)
                    broker.status()  # settles expired leases and requests
            task = asyncio.create_task(tick())
        if mcp is None:
            yield
        else:
            mcp_handler[:] = [_mcp_http_handler(mcp)]
            async with mcp.session_manager.run():
                yield
        if task:
            task.cancel()

    app = FastAPI(title="wanpire", version="1", lifespan=lifespan,
                  description="Make a line behave like a long internet link.")

    def error(code: int, message: str) -> JSONResponse:
        return JSONResponse({"error": message}, status_code=code)

    @app.exception_handler(_Status)
    async def _status(_r: Request, e: _Status):
        return error(e.code, str(e))

    for exc, code in ((UnknownTicket, 404), (NotHolder, 409), (LeaseEnded, 410),
                      (InvalidLink, 422), (InvalidPreset, 422), (InvalidConfig, 422),
                      (RefusedAdapter, 422), (CommandFailed, 500)):
        def handler(_r: Request, e: Exception, code=code):
            return error(code, str(e))
        app.add_exception_handler(exc, handler)

    def authorised(authorization: str | None = Header(default=None)) -> None:
        scheme, _, given = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(given.encode(),
                                                                     token.encode()):
            raise _Status(401, "a bearer token is needed")

    def ticket_of(x_wanpire_ticket: str | None = Header(default=None)) -> str:
        if not x_wanpire_ticket:
            raise _Status(400, f"this call needs the ticket in the {TICKET} header")
        return x_wanpire_ticket

    api = "/api/v1"
    auth = [Depends(authorised)]

    def answer(a) -> dict:
        return {"ticket": a.ticket, "holds": a.holds, "position": a.position,
                "expires_in_s": a.expires_in_s}

    @app.get(f"{api}/status", dependencies=auth)
    def status():
        return {"mode": config.mode, "outbound": outbound, "link": engine.read(outbound),
                "broker": broker.status()}

    @app.post(f"{api}/lease", dependencies=auth)
    def ask(body: dict = Body(...)):
        who, purpose = body.get("who"), body.get("purpose")
        if not who or not purpose:
            raise _Status(422, "asking for the link needs 'who' and 'purpose'")
        return answer(broker.request(str(who), str(purpose)))

    @app.post(f"{api}/lease/poll", dependencies=auth)
    def poll(ticket: str = Depends(ticket_of)):
        a = broker.poll(ticket)
        if a.holds and engine.read(outbound)["down"].get("applied") or \
                a.holds and engine.read(outbound)["up"].get("applied"):
            engine.renew(outbound, lifetime_s=broker.lease_ttl_s)
        return answer(a)

    @app.delete(f"{api}/lease", dependencies=auth, status_code=204)
    def release(ticket: str = Depends(ticket_of)):
        broker.release(ticket)
        return Response(status_code=204)

    @app.delete(f"{api}/lease/holder", dependencies=auth, status_code=204)
    def end_by_hand(body: dict = Body(default={})):
        reason = (body or {}).get("reason") or "no reason given"
        broker.end_lease(str(reason))
        return Response(status_code=204)

    @app.get(f"{api}/link", dependencies=auth)
    def read_link():
        return engine.read(outbound)

    @app.put(f"{api}/link", dependencies=auth)
    def apply_link(body: dict = Body(...), ticket: str = Depends(ticket_of)):
        ends = {"near", "far"} & set(body)
        figures = {"down", "up"} & set(body)
        if ends and figures:
            raise _Status(422, "give either two ends (near, far) or figures (down, up), not both")
        broker.require(ticket)
        account = None
        if ends:
            if ends != {"near", "far"}:
                raise _Status(422, "a link from ends needs both 'near' and 'far'")
            link, account = catalogue.preview(str(body["near"]), str(body["far"]))
        else:
            link = Link.from_dict({k: body[k] for k in figures})
        engine.apply(outbound, link, lifetime_s=broker.lease_ttl_s)
        out = {"link": link.to_dict()}
        if account:
            out["account"] = account
        return out

    @app.delete(f"{api}/link", dependencies=auth, status_code=204)
    def clear_link(ticket: str = Depends(ticket_of)):
        broker.require(ticket)
        engine.clear(outbound)
        return Response(status_code=204)

    @app.get(f"{api}/endpoints", dependencies=auth)
    def endpoints():
        out = []
        for eid in catalogue.endpoint_ids():
            e = catalogue.endpoint(eid)
            out.append({"id": e.id, "name": e.name, "country": e.country, "region": e.region,
                        "default_channel": e.default_channel,
                        "channels": {cid: {"kind": c.kind, "description": c.description}
                                     for cid, c in e.channels.items()}})
        return out

    @app.get(f"{api}/endpoints/{{eid}}", dependencies=auth)
    def endpoint(eid: str):
        if eid not in catalogue.endpoint_ids():
            raise _Status(404, f"no endpoint {eid!r}")
        return catalogue.endpoint_document(eid)

    @app.post(f"{api}/preview", dependencies=auth)
    def preview(body: dict = Body(...)):
        if not body.get("near") or not body.get("far"):
            raise _Status(422, "a preview needs 'near' and 'far'")
        link, account = catalogue.preview(str(body["near"]), str(body["far"]))
        return {"link": link.to_dict(), "account": account}

    @app.get(f"{api}/adapters", dependencies=auth)
    def adapters():
        return [dict(a.to_dict(), role=config.role(a.name)) for a in list_adapters()]

    # the MCP: a client of the routes above, through the app itself (no socket)
    if with_mcp:
        import httpx

        from .mcp_server import make_mcp, rest_client
        mcp = make_mcp(rest_client("http://wanpire", token,
                                   transport=httpx.ASGITransport(app=app)))
        app.state.mcp = mcp
        app.router.routes.append(Route("/mcp", endpoint=_Guard(token, mcp_handler)))

    # last, so /api/v1, /mcp, /docs and /openapi.json win
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
