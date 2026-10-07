# Design: lock the app to its own address

2026-10-07 · approved in chat, part by part

## Goal

Since 2026-10-07 the app runs in the background for the whole login session. Being on
127.0.0.1 keeps other computers out, but not two things already on this PC:

- **Other programs** can send it requests.
- **A web page in Chris's browser using DNS rebinding:** a hostile site points its own
  name at 127.0.0.1, so the browser treats the planner as part of that site. The page
  can then load the planner, read it, and drive it.

After this change the app answers only to requests addressed to it by its own name
(the Host header) and only to live connections started by its own pages (the Origin
header). Normal use looks exactly as it does today. This comes before any phone access.

## Decisions (made with Chris on 2026-10-07)

| Question | Decision |
|---|---|
| Check the Host header only, or Host and Origin? | **Both.** Host stops DNS rebinding; Origin stops another website connecting straight to the app's live connection. |
| How? | **Approach A:** Starlette's own `TrustedHostMiddleware` for Host (the documented tool), plus a small Origin guard of our own (`host_lock.py`), because Starlette has no stock one. |
| Which names are allowed? | **`127.0.0.1` and `localhost`.** Only names that can't leave this PC; never a real internet domain. A later Tailscale name would be one more entry in the same list. |
| Log refused requests? | **No.** Starlette's guard doesn't log either, a hostile page could flood the log, and the browser already shows the reason. |

Rejected: one home-made guard for both headers (rewrites what Starlette ships), and
changing NiceGUI's internal Socket.IO setting `cors_allowed_origins` (not a documented
option, may break on an update, and covers only the live connection).

### Facts checked (2026-10-07)

Read as page text in the built-in browser, or in the installed library code in `.venv/`:

- **FastAPI, Advanced Middleware** (fastapi.tiangolo.com/advanced/middleware/):
  `app.add_middleware(TrustedHostMiddleware, allowed_hosts=[...])` "Enforces that all
  incoming requests have a correctly set Host header". A request that fails gets a 400.
  `www_redirect` defaults to True. **Starlette, Middleware** (starlette.dev/middleware/,
  the docs moved there from starlette.io) says the same and documents "pure ASGI
  middleware", the style `host_lock.py` uses.
- **NiceGUI, Security Best Practices** (nicegui.io/documentation/section_security):
  rendering a page mints a fresh `client_id` and embeds it in the page; anyone who knows it
  can send events on behalf of that client. "Secure pages, not /_nicegui/." That is why the
  Host check matters: a rebinding page could read the `client_id` from a loaded page.
- **ASGI spec, HTTP & WebSocket** (asgi.readthedocs.io/en/latest/specs/www.html): if an app
  sends `websocket.close` before accepting, the server must answer HTTP 403 and not complete
  the handshake. Request header names "should be lowercased, but it is not required", so the
  guard compares them ignoring case.
- **Installed code** (NiceGUI 3.17.1, Starlette 1.7.0, python-engineio 4.14.0):
  - `TrustedHostMiddleware` checks both `http` and `websocket` requests, and compares only
    the host name, not the port.
  - NiceGUI's `app` is a FastAPI app. Its live connection is Socket.IO, mounted inside that
    app at `/_nicegui_ws/` with `cors_allowed_origins='*'` (any website may connect).
  - NiceGUI's own two middlewares (`RedirectWithPrefixMiddleware`, `SetCacheControlMiddleware`)
    only adjust responses after the app has answered, so our guards decide every request
    wherever they sit in the line.
  - Starlette refuses `add_middleware` once the app has started, so the guards are added
    before `ui.run`.
- **`tools/open_planner.py`:** the icon's "is it running?" check asks urllib for
  `http://127.0.0.1:8080` (right Host, no Origin) and counts any answer, even an error page,
  as running.
- **Tests** run with the system `python3` and never import `app.py`, NiceGUI or Starlette.

## 1. What changes

### `app.py`

Beside `HOST` and `PORT`:

```python
ALLOWED_HOSTS = [HOST, "localhost"]   # the names this app answers to; anything else is refused
```

In the "Start" section, beside `app.add_static_files(...)` and before `ui.run`:

```python
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)
app.add_middleware(OriginLock, allowed_origins=allowed_origins(ALLOWED_HOSTS, PORT))
```

`TrustedHostMiddleware` is imported from `fastapi.middleware.trustedhost` (as FastAPI's page
shows; `app.py` already imports from `fastapi`). `www_redirect=False` switches off a feature
that is never wanted here. The module docstring's last line gains a sentence on the lock.

### `host_lock.py` (new, standard library only)

- `allowed_origins(names, port)` returns the allowed Origin values, one per name:
  `{"http://127.0.0.1:8080", "http://localhost:8080"}`. Built from `PORT`, so a test copy on
  8091 allows `:8091` by itself.
- `origin_allowed(origin, allowed)` returns True when `origin` is `None` (no Origin header:
  typing an address, clicking a link, the icon's check, curl), or when it exactly matches one
  of `allowed`. Everything else is False, including `null` (sent by sandboxed pages and local
  files), the right name with another port, and `https://`.
- `OriginLock`, a pure ASGI middleware (`__init__(self, app, allowed_origins)` and
  `async __call__(self, scope, receive, send)`):
  - For `http` and `websocket` requests, it reads every header whose name is `origin`
    (any case). If any of them is not allowed, the request is refused and the app is never
    called. Otherwise the request goes to the app untouched.
  - **Refused page request:** status 403, `content-type: text/plain; charset=utf-8`,
    body `Refused: this request came from another website.`
  - **Refused live connection:** it waits for the `websocket.connect` message, then sends
    `websocket.close` before accepting, so the server answers 403 (ASGI spec).
  - Any other request type (`lifespan`: start-up and shutdown) passes straight through.

### README

One line under "Good to know": the app answers only when addressed as `127.0.0.1` or
`localhost`, and refuses requests started by other websites, so web pages can't use it
behind your back.

### What does not change

Every screen, the data files, the icon, the installer, the service, the terminal scripts.
The icon's check, the installer's check, typing `localhost:8080`, the terminal way, and test
copies on 8091 all keep working.

## 2. What a refused request sees

| Who's asking | Answer |
|---|---|
| Wrong Host name (DNS rebinding, or any other name) | 400, Starlette's fixed text `Invalid host header` |
| Foreign Origin on a page request | 403, `Refused: this request came from another website.` |
| Foreign Origin on the live connection | 403 during the handshake; the other site sees a failed connection |

Nothing is logged.

## 3. Testing and proof

### Automatic tests (`tests/test_host_lock.py`)

Standard library only; fake ASGI messages, run with `asyncio`.

- `allowed_origins`: exactly the two values for port 8080; `:8091` for port 8091.
- `origin_allowed`: True for `None` and both allowed values. False for a foreign site,
  `null`, `http://127.0.0.1:9999`, and `https://127.0.0.1:8080`.
- `OriginLock`, page request: an allowed Origin and no Origin reach the app unchanged
  (the app receives the same scope); a foreign Origin gets the 403 and the text, and the app
  is never called.
- `OriginLock`, live connection: a foreign Origin gets `websocket.close` before any accept,
  and the app is never called; an allowed Origin reaches the app.
- `OriginLock`: two Origin headers, one foreign, is refused; a header name written `Origin`
  (capital O) is still checked.
- `OriginLock`: a `lifespan` request passes straight through.
- A text check on `app.py` (same style as `test_host_and_port_match_app_py`): it adds
  `TrustedHostMiddleware` with `allowed_hosts=ALLOWED_HOSTS` and `www_redirect=False`, adds
  `OriginLock`, and `ALLOWED_HOSTS = [HOST, "localhost"]`.
- Once the new file passes, break the guard on purpose once or twice to prove the tests can
  fail, then restore it.

All 190 existing tests must still pass; `python3 check_methods.py` must still be clean.

### Proof that the screens don't change (frozen copy on port 8091)

In `.superpowers/sdd/host-lock/` (git-ignored): re-create `run_frozen.py` (patches
`rs3_planner.load_profile` / `load_quests` with frozen RuneMetrics replies before anything
imports them, asserts `player_cache` got the patched ones) and run a copy of the project on
port 8091.

- **Before** the change: save the page text of all 8 screens (`/player`, `/`, `/play`,
  `/plan`, `/skills`, `/quests`, `/quests/goal`, `/progress`) in the preview browser's
  localStorage, with a SHA-256 fingerprint of each on disk.
- **After:** the same 8 texts must match exactly.
- Live actions that need the live connection (choose hours, **Show my plan**, **Change
  goal**) at both `http://127.0.0.1:8091` and `http://localhost:8091`; the browser console
  shows no errors.
- The throwaway copy is deleted afterwards (it holds copies of Chris's data).

### Proof that the locks work (curl, on the 8091 copy)

- `curl --resolve evil.example:8091:127.0.0.1 http://evil.example:8091/` (sends
  `evil.example` as the Host, as a rebinding page would): 400 `Invalid host header`.
  The same page as `127.0.0.1`: 200.
- A page request with `Origin: http://evil.example`: 403 with the refusal text.
- The live connection with `Origin: http://evil.example`, both forms: the websocket
  handshake (`/_nicegui_ws/socket.io/?EIO=4&transport=websocket`) and the HTTP polling
  fallback (`?EIO=4&transport=polling`): 403. The same with `Origin: http://127.0.0.1:8091`:
  accepted.

### Chris's live app

After the code is committed, Chris uses **Restart** on the icon (or approves
`systemctl --user restart rs3-planner`). Then: all 8 screens at `http://127.0.0.1:8080` in
the built-in browser, and one curl Host-refusal check against port 8080 (read-only).
Pushing to GitHub only when Chris says so.

## Out of scope

- Tailscale, phone access, any name besides `127.0.0.1` and `localhost`.
- HTTPS, logins, rate limiting.
- Logging refusals.
- Changing NiceGUI's own Socket.IO settings.
