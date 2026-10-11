"""wanpire's REST API: the engine's only interface. The web UI and the MCP are its clients.

The box has one account (``account.py``). Until it exists only ``setup`` answers, and the
first visit makes it; afterwards every route under ``/api/v1`` needs it, in HTTP Basic
credentials (agents, scripts) or a browser's session cookie. Changes to the link need the
broker's lease, shown by its ticket in ``X-Wanpire-Ticket``; reading needs no ticket.

    GET    /api/v1/setup             {"needed"}: whether the box still has no account
    POST   /api/v1/setup             {"user", "password"}: make it, once; signs the browser in
    POST   /api/v1/session           {"user", "password"}: sign a browser in (a cookie)
    GET    /api/v1/session           who is signed in
    DELETE /api/v1/session           sign out
    PUT    /api/v1/account/password  {"current", "new"}: ends every other session
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

The web UI's static files are served at ``/`` without credentials: they hold no data, and the
page itself calls the routes above with its session.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import secrets
import threading
import time
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

from . import catalogue
from .account import Account, InvalidAccount, check
from .broker import Broker, LeaseEnded, NotHolder, UnknownTicket
from .config import Config, InvalidConfig
from .engine import CommandFailed, RefusedAdapter
from .model import InvalidLink, Link
from .presets import InvalidPreset

TICKET = "X-Wanpire-Ticket"
COOKIE = "wanpire_session"
WEB = Path(__file__).parent / "web"
NO_ACCOUNT = ("the box has no account yet: open its web page to make one, "
              "or run `sudo wanpire account set <user>` on the box")


class _Status(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _basic(authorization: str | None) -> tuple[str, str] | None:
    """The user and password of an ``Authorization: Basic`` header, or None."""
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        user, sep, password = base64.b64decode(value.strip(), validate=True).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return None
    return (user, password) if sep else None


def _mcp_http_handler(mcp):
    """The SDK's streamable HTTP handler for ``mcp``: stateless, JSON answers."""
    from mcp.server.transport_security import TransportSecuritySettings
    http = mcp.streamable_http_app(
        streamable_http_path="/mcp", stateless_http=True, json_response=True,
        # /mcp takes Basic only, never the web page's cookie, so another site's page cannot
        # ride a signed-in browser; the host check would only refuse the box's own names
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    return next(r.endpoint for r in http.routes if getattr(r, "path", None) == "/mcp")


class _Guard:
    """An ASGI app: the box's account in Basic credentials, then the MCP's handler."""

    def __init__(self, allowed, handler: list):
        self._allowed = allowed  # a callable(authorization header) -> None, raising _Status
        self._handler = handler

    async def __call__(self, scope, receive, send):
        given = dict(scope.get("headers") or []).get(b"authorization", b"").decode("latin-1")
        try:
            await asyncio.to_thread(self._allowed, given)
        except _Status as e:
            await JSONResponse({"error": str(e)}, status_code=e.code)(scope, receive, send)
            return
        if not self._handler:
            await JSONResponse({"error": "the MCP is starting"}, status_code=503)(
                scope, receive, send)
            return
        await self._handler[0](scope, receive, send)


def create_app(engine, broker: Broker, config: Config, account: Account, list_adapters,
               tick_s: float | None = 5.0, with_mcp: bool = True,
               fail_delay_s: float = 0.5) -> FastAPI:
    outbound = config.outbound[0]
    # the MCP on the box calls the routes in process with this, made here and never written
    internal = secrets.token_urlsafe(32)
    sessions: dict[str, tuple] = {}  # session id -> the account's generation it was made under
    sessions_lock = threading.Lock()

    def refused(message: str = "the box's user name and password are needed"):
        if fail_delay_s:
            time.sleep(fail_delay_s)  # slows guessing; no lockout a stranger could trigger
        return _Status(401, message)

    def session_user(sid: str | None) -> str | None:
        if not sid:
            return None
        with sessions_lock:
            gen = sessions.get(sid)
        if gen is None or gen != account.generation:
            return None
        return account.user

    def new_session(response: Response) -> None:
        sid = secrets.token_urlsafe(32)
        with sessions_lock:
            sessions[sid] = account.generation
        response.set_cookie(COOKIE, sid, httponly=True, samesite="strict", path="/")

    def basic_or_internal(authorization: str) -> None:
        if not account.exists():
            raise _Status(403, NO_ACCOUNT)
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and secrets.compare_digest(value.encode(), internal.encode()):
            return
        pair = _basic(authorization)
        if pair is None:
            raise _Status(401, "the box's user name and password are needed")
        if not account.verify(*pair):
            raise refused("the user name or the password was refused")

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
                      (RefusedAdapter, 422), (CommandFailed, 500), (InvalidAccount, 422)):
        def handler(_r: Request, e: Exception, code=code):
            return error(code, str(e))
        app.add_exception_handler(exc, handler)

    def authorised(request: Request, authorization: str | None = Header(default=None)) -> None:
        if not account.exists():
            raise _Status(403, NO_ACCOUNT)
        if authorization:
            basic_or_internal(authorization)
        elif session_user(request.cookies.get(COOKIE)) is None:
            raise _Status(401, "the box's user name and password are needed")

    def ticket_of(x_wanpire_ticket: str | None = Header(default=None)) -> str:
        if not x_wanpire_ticket:
            raise _Status(400, f"this call needs the ticket in the {TICKET} header")
        return x_wanpire_ticket

    api = "/api/v1"
    auth = [Depends(authorised)]

    def answer(a) -> dict:
        return {"ticket": a.ticket, "holds": a.holds, "position": a.position,
                "expires_in_s": a.expires_in_s}

    # -- the account ----------------------------------------------------------------------

    def credentials(body: dict) -> tuple[str, str]:
        return str(body.get("user") or ""), str(body.get("password") or "")

    @app.get(f"{api}/setup")
    def setup_needed():
        return {"needed": not account.exists()}

    @app.post(f"{api}/setup", status_code=201)
    def setup(response: Response, body: dict = Body(...)):
        if account.exists():
            raise _Status(409, "the box has an account already; sign in")
        user, password = credentials(body)
        check(user, password)
        if not account.create(user, password):
            raise _Status(409, "the box has an account already; sign in")
        new_session(response)
        return {"user": user}

    @app.post(f"{api}/session")
    def sign_in(response: Response, body: dict = Body(...)):
        if not account.exists():
            raise _Status(403, NO_ACCOUNT)
        if not account.verify(*credentials(body)):
            raise refused("the user name or the password was refused")
        new_session(response)
        return {"user": account.user}

    @app.get(f"{api}/session")
    def signed_in(request: Request):
        user = session_user(request.cookies.get(COOKIE))
        if user is None:
            if not account.exists():
                raise _Status(403, NO_ACCOUNT)
            raise _Status(401, "not signed in")
        return {"user": user}

    @app.delete(f"{api}/session", status_code=204)
    def sign_out(request: Request):
        with sessions_lock:
            sessions.pop(request.cookies.get(COOKIE) or "", None)
        r = Response(status_code=204)
        r.delete_cookie(COOKIE, path="/")
        return r

    @app.put(f"{api}/account/password", dependencies=auth)
    def change_password(request: Request, body: dict = Body(...)):
        current, new = str(body.get("current") or ""), str(body.get("new") or "")
        user = account.user
        if not account.verify(user, current):
            raise refused("the current password was refused")
        account.set(user, new)  # raises InvalidAccount (422) for a short one
        r = Response(status_code=204)
        with sessions_lock:
            sessions.clear()  # every session but this one ends: they were under the old one
        if request.cookies.get(COOKIE):
            new_session(r)
        return r

    # -- the box ----------------------------------------------------------------------------

    # how the link now applied was described (R7); dropped once the engine reports none
    described: list = [None]

    @app.get(f"{api}/status", dependencies=auth)
    def status():
        b = broker.status()  # first: it may clear an expired lease's link
        link = engine.read(outbound)
        if not (link["down"].get("applied") or link["up"].get("applied")):
            described[0] = None
        return {"mode": config.mode, "outbound": outbound, "link": link,
                "applied": described[0], "broker": b}

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
        described[0] = ({"figures": True} if account is None else
                        {end: f"{account[end]['endpoint']}:{account[end]['channel']}"
                         for end in ("near", "far")})
        out = {"link": link.to_dict()}
        if account:
            out["account"] = account
        return out

    @app.delete(f"{api}/link", dependencies=auth, status_code=204)
    def clear_link(ticket: str = Depends(ticket_of)):
        broker.require(ticket)
        engine.clear(outbound)
        described[0] = None
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
        mcp = make_mcp(rest_client("http://wanpire", bearer=internal,
                                   transport=httpx.ASGITransport(app=app)))
        app.state.mcp = mcp
        app.router.routes.append(Route("/mcp", endpoint=_Guard(basic_or_internal, mcp_handler)))

    # last, so /api/v1, /mcp, /docs and /openapi.json win
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
