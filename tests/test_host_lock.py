"""Tests for host_lock.py (the Origin lock).

Requests here are fake ASGI messages (the plain dictionaries a Python web server
hands to an app): nothing starts a server or uses the network.
"""

import asyncio
import re
import unittest
from pathlib import Path

import host_lock

PROJECT = Path(__file__).resolve().parent.parent

ALLOWED = host_lock.allowed_origins(["127.0.0.1", "localhost"], 8080)
FOREIGN = b"http://evil.example"


def request(kind, *headers):
    """A fake request of one kind ("http", "websocket" or "lifespan") with these headers."""
    return {"type": kind, "path": "/", "headers": list(headers)}


class FakeApp:
    """Stands in for the planner behind the lock and writes down every request it gets."""

    def __init__(self):
        self.scopes = []

    async def __call__(self, scope, receive, send):
        self.scopes.append(scope)


def run_lock(scope, incoming=()):
    """
    Send one request through OriginLock.
    Returns (the requests the app got, the messages the lock sent back).
    `incoming` are the messages the lock can receive (e.g. websocket.connect).
    """
    app, sent, messages = FakeApp(), [], list(incoming)

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    asyncio.run(host_lock.OriginLock(app, ALLOWED)(scope, receive, send))
    return app.scopes, sent


class AllowedOriginsTests(unittest.TestCase):
    def test_two_names_on_8080(self):
        self.assertEqual(ALLOWED, {"http://127.0.0.1:8080", "http://localhost:8080"})

    def test_follows_the_port(self):
        self.assertEqual(host_lock.allowed_origins(["127.0.0.1", "localhost"], 8091),
                         {"http://127.0.0.1:8091", "http://localhost:8091"})


class OriginAllowedTests(unittest.TestCase):
    def test_no_origin_is_allowed(self):
        self.assertTrue(host_lock.origin_allowed(None, ALLOWED))

    def test_the_apps_own_origins_are_allowed(self):
        self.assertTrue(host_lock.origin_allowed("http://127.0.0.1:8080", ALLOWED))
        self.assertTrue(host_lock.origin_allowed("http://localhost:8080", ALLOWED))

    def test_another_website_is_refused(self):
        self.assertFalse(host_lock.origin_allowed("http://evil.example", ALLOWED))

    def test_null_is_refused(self):
        self.assertFalse(host_lock.origin_allowed("null", ALLOWED))

    def test_another_port_is_refused(self):
        self.assertFalse(host_lock.origin_allowed("http://127.0.0.1:9999", ALLOWED))

    def test_https_is_refused(self):
        self.assertFalse(host_lock.origin_allowed("https://127.0.0.1:8080", ALLOWED))


class PageRequestTests(unittest.TestCase):
    def test_no_origin_reaches_the_app(self):
        scope = request("http", (b"host", b"127.0.0.1:8080"))
        self.assertEqual(run_lock(scope), ([scope], []))

    def test_the_apps_own_origin_reaches_the_app(self):
        scope = request("http", (b"origin", b"http://localhost:8080"))
        self.assertEqual(run_lock(scope), ([scope], []))

    def test_another_website_gets_403_and_the_app_never_sees_it(self):
        scopes, sent = run_lock(request("http", (b"origin", FOREIGN)))
        self.assertEqual(scopes, [])
        self.assertEqual(sent[0]["type"], "http.response.start")
        self.assertEqual(sent[0]["status"], 403)
        self.assertIn((b"content-type", b"text/plain; charset=utf-8"), sent[0]["headers"])
        self.assertEqual(sent[1], {"type": "http.response.body",
                                   "body": host_lock.REFUSAL_TEXT.encode("utf-8")})

    def test_a_capitalised_header_name_is_still_checked(self):
        scopes, sent = run_lock(request("http", (b"Origin", FOREIGN)))
        self.assertEqual((scopes, sent[0]["status"]), ([], 403))

    def test_two_origins_one_foreign_is_refused(self):
        scope = request("http", (b"origin", b"http://127.0.0.1:8080"), (b"origin", FOREIGN))
        scopes, sent = run_lock(scope)
        self.assertEqual((scopes, sent[0]["status"]), ([], 403))


class LiveConnectionTests(unittest.TestCase):
    def test_another_website_is_closed_before_accepting(self):
        scopes, sent = run_lock(request("websocket", (b"origin", FOREIGN)),
                                incoming=[{"type": "websocket.connect"}])
        self.assertEqual(scopes, [])
        self.assertEqual(sent, [{"type": "websocket.close"}])   # no websocket.accept before it

    def test_the_apps_own_origin_reaches_the_app(self):
        scope = request("websocket", (b"origin", b"http://127.0.0.1:8080"))
        self.assertEqual(run_lock(scope), ([scope], []))


class LifespanTests(unittest.TestCase):
    def test_start_up_and_shutdown_pass_straight_through(self):
        scope = {"type": "lifespan"}
        self.assertEqual(run_lock(scope), ([scope], []))

class AppWiringTests(unittest.TestCase):
    """app.py can't be imported here (it starts NiceGUI), so read it as text."""

    def setUp(self):
        self.text = (PROJECT / "app.py").read_text(encoding="utf-8")

    def test_allowed_hosts_are_this_computers_two_names(self):
        self.assertRegex(self.text, r'(?m)^ALLOWED_HOSTS = \[HOST, "localhost"\]')

    def test_host_lock_is_switched_on_before_ui_run(self):
        line = "app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS, www_redirect=False)"
        # Inside switch_on_locks, at a line's start: a commented-out line doesn't count.
        self.assertTrue(re.search(r"(?m)^    " + re.escape(line), self.text), "the Host lock must be switched on")
        self.assertLess(self.text.index(line), self.text.index("ui.run("))

    def test_origin_lock_is_switched_on_with_the_chosen_port(self):
        line = "app.add_middleware(OriginLock, allowed_origins=allowed_origins(ALLOWED_HOSTS, port))"
        self.assertTrue(re.search(r"(?m)^    " + re.escape(line), self.text),
                        "the Origin lock must be built from the port the app really uses")
        self.assertLess(self.text.index(line), self.text.index("ui.run("))


if __name__ == "__main__":
    unittest.main()
