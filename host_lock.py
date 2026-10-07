"""
RS3 Planner - the Origin lock
=============================

Refuses requests that another website started.

When a web page talks to a server, the browser adds an "Origin" label naming
the site the page came from (for example "https://evil.example"). The
planner's own pages carry "http://127.0.0.1:8080" or "http://localhost:8080".
Anything else means some other website is trying to use the planner behind
your back, so the request is refused before the app sees it.

Requests with no Origin label pass: typing the address, clicking a link, the
app icon's "is it running?" check and curl don't send one.

This is one of two locks, both switched on in app.py. The other, Starlette's
TrustedHostMiddleware, refuses requests addressed to the app by any other
name, which stops "DNS rebinding" web pages. This one checks each request
first: app.add_middleware puts the guard added last at the front of the line.
So a request that fails both checks gets this lock's 403, not the Host lock's 400.

Standard library only, so the tests can load it without NiceGUI.
"""

REFUSAL_TEXT = "Refused: this request came from another website."


def allowed_origins(names, port):
    """The Origin labels the app's own pages send: one per name, e.g. 'http://127.0.0.1:8080'."""
    return {f"http://{name}:{port}" for name in names}


def origin_allowed(origin, allowed):
    """
    True when a request may go ahead: it has no Origin label (origin is None),
    or the label is exactly one of `allowed`. Everything else is refused,
    including 'null' (what sandboxed pages and local files send).
    """
    return origin is None or origin in allowed


def origins_in(scope):
    """Every Origin label on a request, as text. Header names may arrive in any case."""
    return [value.decode("latin-1") for name, value in scope.get("headers", [])
            if name.lower() == b"origin"]


class OriginLock:
    """
    A guard in front of the whole app (an "ASGI middleware": the standard way
    to wrap a Python web app, see starlette.dev/middleware/). It checks page
    requests ("http") and live connections ("websocket"). Anything else, such
    as start-up and shutdown ("lifespan"), passes straight through.
    """

    def __init__(self, app, allowed_origins):
        self.app = app                       # the app (or the next guard) behind this one
        self.allowed = set(allowed_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            if not all(origin_allowed(origin, self.allowed) for origin in origins_in(scope)):
                await refuse(scope, receive, send)
                return                       # the app never sees a refused request
        await self.app(scope, receive, send)


async def refuse(scope, receive, send):
    """Answer a refused request without passing it on."""
    if scope["type"] == "http":
        body = REFUSAL_TEXT.encode("utf-8")
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                (b"content-length", str(len(body)).encode("ascii"))]})
        await send({"type": "http.response.body", "body": body})
    else:
        # A live connection: wait for its opening message, then close it before
        # accepting. The web server then answers 403 (ASGI spec).
        await receive()                      # "websocket.connect"
        await send({"type": "websocket.close"})
