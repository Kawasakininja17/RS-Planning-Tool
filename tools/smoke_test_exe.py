#!/usr/bin/env python3
"""
RS3 Planner - smoke test for the built app
==========================================

Starts the app that tools/build_exe.py made and checks it from outside:
  - it answers on port 8095 as RS3 Planner, prints its version line, and makes
    its data folder in a scratch folder (never the real one; the scratch path
    has a space and an accent, like many Windows user folders);
  - the host lock still refuses other names and other websites;
  - a second copy notices the first, says so and ends;
  - nothing was fetched from RuneMetrics (a fresh start has no player yet).
Then it stops the app. Run it with any Python 3, from the project folder:
    python3 tools/smoke_test_exe.py
Exit code 0 means every check passed. The app's output is kept in build/smoke-logs/.

The app opens a browser tab by itself, twice (the second copy opens the first),
exactly as it would for a clan member.

Standard library only.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))   # to reuse bundle.py's "is RS3 Planner answering?" check
from bundle import PREFERRED_PORT, planner_answers   # noqa: E402

APP_DIR = PROJECT / "dist" / "RS3 Planner"
APP = APP_DIR / ("RS3 Planner.exe" if sys.platform == "win32" else "RS3 Planner")
SCRATCH = PROJECT / "build" / "smoke data é"
DATA_FOLDER = SCRATCH / ("RS3 Planner" if sys.platform == "win32" else "rs3-planner")
LOGS = PROJECT / "build" / "smoke-logs"
BASE = f"http://127.0.0.1:{PREFERRED_PORT}"
START_WAIT = 90   # seconds: a first start can be slow (e.g. a virus scan of the new files)

failures = []


def check(what, passed, detail=""):
    print(f"  {'PASS' if passed else 'FAIL'}  {what}" + (f"  ({detail})" if detail and not passed else ""), flush=True)
    if not passed:
        failures.append(what)


def status(path, headers=None):
    """(HTTP status, body) for one request to the app, never through a proxy."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(BASE + path, headers=headers or {})
    try:
        with opener.open(request, timeout=10) as reply:
            return reply.status, reply.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def websocket_first_line(origin):
    """Open the app's live connection with this Origin; the server's first answer line."""
    handshake = (f"GET /_nicegui_ws/socket.io/?EIO=4&transport=websocket HTTP/1.1\r\n"
                 f"Host: 127.0.0.1:{PREFERRED_PORT}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n"
                 f"Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                 f"Origin: {origin}\r\n\r\n")
    with socket.create_connection(("127.0.0.1", PREFERRED_PORT), timeout=5) as conn:
        conn.sendall(handshake.encode("ascii"))
        return conn.recv(4096).decode("latin-1").splitlines()[0]


def read_log(name):
    return (LOGS / name).read_text(encoding="utf-8", errors="replace")


def main():
    if not APP.is_file():
        sys.exit(f"No built app at {APP}: run tools/build_exe.py first.")
    if planner_answers(PREFERRED_PORT) or status_answers():
        sys.exit(f"Something already answers on port {PREFERRED_PORT}: stop it first.")
    shutil.rmtree(SCRATCH, ignore_errors=True)
    shutil.rmtree(LOGS, ignore_errors=True)
    SCRATCH.mkdir(parents=True)
    LOGS.mkdir(parents=True)
    env = dict(os.environ, LOCALAPPDATA=str(SCRATCH), XDG_DATA_HOME=str(SCRATCH))

    print(f"Starting {APP.name} (data in a scratch folder)", flush=True)
    with open(LOGS / "first.log", "w", encoding="utf-8") as log:
        first = subprocess.Popen([str(APP)], cwd=APP_DIR, env=env, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + START_WAIT
        while not planner_answers(PREFERRED_PORT) and time.monotonic() < deadline and first.poll() is None:
            time.sleep(1)
        check(f"answers on {PREFERRED_PORT} as RS3 Planner", planner_answers(PREFERRED_PORT),
              "see build/smoke-logs/first.log")
        if failures:
            return
        log_text = read_log("first.log")
        check("prints its version line", "RS3 Planner 20" in log_text)
        check("prints where data is saved", "Your saved data: " in log_text)
        check("made its data folder in the scratch folder", DATA_FOLDER.is_dir(), str(DATA_FOLDER))
        check("Choose player page: 200", status("/player")[0] == 200)
        check("another name (rebinding): 400",
              status("/player", {"Host": f"evil.example:{PREFERRED_PORT}"})[0] == 400)
        check("another website's page request: 403", status("/player", {"Origin": "http://evil.example"})[0] == 403)
        check("another website's live connection: 403", " 403 " in websocket_first_line("http://evil.example"))
        check("its own live connection: 101",
              " 101 " in websocket_first_line(f"http://127.0.0.1:{PREFERRED_PORT}"))

        try:
            with open(LOGS / "second.log", "w", encoding="utf-8") as log:
                second = subprocess.run([str(APP)], cwd=APP_DIR, env=env, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=60)
            ended = second.returncode
        except subprocess.TimeoutExpired:   # subprocess.run has already stopped it
            ended = "still running after 60 seconds"
        check("a second copy ends by itself", ended == 0, f"exit code {ended}")
        check("a second copy says it's already running", "already running" in read_log("second.log"))
        check("nothing fetched from RuneMetrics", "Fetching " not in read_log("first.log"))
    finally:
        first.terminate()
        try:
            first.wait(timeout=20)
        except subprocess.TimeoutExpired:
            first.kill()
    check("stopped", not planner_answers(PREFERRED_PORT))


def status_answers():
    """True if anything at all accepts a connection on the port."""
    try:
        with socket.create_connection(("127.0.0.1", PREFERRED_PORT), timeout=2):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    main()
    if failures:
        print(f"\n{len(failures)} check(s) failed. The app's output is in build/smoke-logs/.")
        sys.exit(1)
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print("\nEvery check passed.")
