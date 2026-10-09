"""Tests for bundle.py (running as the Windows app).

Nothing here uses the internet or the real home folder: the outside world is
passed in as fakes. The read_page tests use tiny servers on 127.0.0.1 only.
"""

import io
import re
import socket
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import bundle

PROJECT = Path(__file__).resolve().parent.parent
HOME = Path("/home/fake")   # never the real home folder


class IsBundledTests(unittest.TestCase):
    def test_tests_run_from_source(self):
        self.assertFalse(bundle.is_bundled())

    def test_bundle_has_frozen_and_meipass(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "_MEIPASS", "/fake/_internal", create=True):
            self.assertTrue(bundle.is_bundled())

    def test_frozen_alone_is_not_a_pyinstaller_bundle(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertFalse(bundle.is_bundled())


class StopTests(unittest.TestCase):
    def test_from_source_it_prints_and_exits_without_waiting(self):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch("builtins.input") as asked, \
                self.assertRaises(SystemExit) as stopped:
            bundle.stop("Something went wrong.")
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(out.getvalue(), "Something went wrong.\n")
        asked.assert_not_called()

    def test_in_a_bundle_it_waits_for_enter(self):
        with redirect_stdout(io.StringIO()), mock.patch.object(bundle, "is_bundled", return_value=True), \
                mock.patch("builtins.input") as asked, self.assertRaises(SystemExit):
            bundle.stop("Something went wrong.")
        asked.assert_called_once_with("Press Enter to close.")

    def test_in_a_bundle_with_no_keyboard_it_still_exits(self):
        with redirect_stdout(io.StringIO()), mock.patch.object(bundle, "is_bundled", return_value=True), \
                mock.patch("builtins.input", side_effect=EOFError), self.assertRaises(SystemExit) as stopped:
            bundle.stop("Something went wrong.")
        self.assertEqual(stopped.exception.code, 1)


class UserDataDirTests(unittest.TestCase):
    def test_windows_uses_localappdata(self):
        env = {"LOCALAPPDATA": r"C:\Users\Some Player\AppData\Local"}
        self.assertEqual(bundle.user_data_dir(env, "win32", HOME),
                         Path(r"C:\Users\Some Player\AppData\Local") / "RS3 Planner")

    def test_windows_folder_with_spaces_and_accents(self):
        env = {"LOCALAPPDATA": "C:\\Users\\José Ñúñez\\AppData\\Local"}
        self.assertEqual(bundle.user_data_dir(env, "win32", HOME),
                         Path("C:\\Users\\José Ñúñez\\AppData\\Local") / "RS3 Planner")

    def test_windows_without_localappdata_stops_with_a_message(self):
        for env in ({}, {"LOCALAPPDATA": ""}):
            out = io.StringIO()
            with redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
                bundle.user_data_dir(env, "win32", HOME)
            self.assertEqual(stopped.exception.code, 1)
            self.assertIn("LOCALAPPDATA", out.getvalue())

    def test_linux_uses_xdg_data_home(self):
        self.assertEqual(bundle.user_data_dir({"XDG_DATA_HOME": "/x/data"}, "linux", HOME),
                         Path("/x/data/rs3-planner"))

    def test_linux_unset_or_empty_uses_local_share(self):
        for env in ({}, {"XDG_DATA_HOME": ""}):
            self.assertEqual(bundle.user_data_dir(env, "linux", HOME),
                             HOME / ".local" / "share" / "rs3-planner")

    def test_other_systems_stop_with_a_message(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            bundle.user_data_dir({}, "darwin", HOME)
        self.assertIn("Windows and Linux only", out.getvalue())


class VersionTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "version.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_line_without_its_line_break(self):
        self.file.write_text("RS3 Planner 2026-10-12 (ea96c3c)\n", encoding="utf-8")
        self.assertEqual(bundle.version_text(self.file), "RS3 Planner 2026-10-12 (ea96c3c)")

    def test_no_file_means_none(self):
        self.assertIsNone(bundle.version_text(self.file))

    def test_blank_file_means_none(self):
        self.file.write_text("  \n", encoding="utf-8")
        self.assertIsNone(bundle.version_text(self.file))

    def test_garbled_file_means_none(self):
        self.file.write_bytes(b"\xff\xfe\x00garbage")
        self.assertIsNone(bundle.version_text(self.file))

    def test_from_source_there_is_no_version_file(self):
        self.assertEqual(bundle.VERSION_FILE, Path(bundle.__file__).parent / "version.txt")
        self.assertIsNone(bundle.version_text())


class OneShotServer:
    """A tiny server on 127.0.0.1 (this computer only) that answers one connection
    with `reply`, or says nothing at all when reply is None."""

    def __init__(self, reply):
        self.reply = reply
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))   # 0: any free port
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:   # closed before anyone connected
            return
        with conn:
            conn.recv(4096)
            if self.reply is None:
                time.sleep(1)   # silent until the caller has given up
            else:
                conn.sendall(self.reply)

    def close(self):
        self.sock.close()


class ReadPageTests(unittest.TestCase):
    def ask(self, reply, timeout=2):
        server = OneShotServer(reply)
        try:
            return bundle.read_page(f"http://127.0.0.1:{server.port}/player", timeout=timeout)
        finally:
            server.close()

    def test_a_real_page_is_read(self):
        page = self.ask(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n"
                        b"<title>Choose player - RS3 Planner</title>")
        self.assertIn("<title>Choose player - RS3 Planner</title>", page)

    def test_garbage_means_none(self):
        self.assertIsNone(self.ask(b"garbage\r\n\r\n"))

    def test_silence_means_none(self):
        self.assertIsNone(self.ask(None, timeout=0.3))

    def test_nothing_listening_means_none(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        # The port was free a moment ago and nothing listens on it now.
        self.assertIsNone(bundle.read_page(f"http://127.0.0.1:{port}/player"))


class PlannerAnswersTests(unittest.TestCase):
    def test_rs3_planner_page(self):
        asked = []

        def fetch(url):
            asked.append(url)
            return "<html><head><title>Choose player - RS3 Planner</title></head></html>"

        self.assertTrue(bundle.planner_answers(8095, fetch))
        self.assertEqual(asked, ["http://127.0.0.1:8095/player"])

    def test_another_programs_page(self):
        self.assertFalse(bundle.planner_answers(8095, lambda url: "<title>Media server</title>"))

    def test_nothing_answers(self):
        self.assertFalse(bundle.planner_answers(8095, lambda url: None))

    def test_the_name_outside_the_title_does_not_count(self):
        page = "<title>My notes</title><p>RS3 Planner</p>"
        self.assertFalse(bundle.planner_answers(8095, lambda url: page))


class ChoosePortTests(unittest.TestCase):
    def test_already_running_on_8095(self):
        def find_free(first, last):
            raise AssertionError("no port search when RS3 Planner already runs")

        self.assertEqual(bundle.choose_port(lambda port: True, find_free), (True, 8095))

    def test_8095_free(self):
        searched = []

        def find_free(first, last):
            searched.append((first, last))
            return first

        self.assertEqual(bundle.choose_port(lambda port: False, find_free), (False, 8095))
        self.assertEqual(searched, [(8095, 8999)])

    def test_8095_taken_by_another_program(self):
        self.assertEqual(bundle.choose_port(lambda port: False, lambda first, last: 8096), (False, 8096))


class AppStartTests(unittest.TestCase):
    """app.py can't be imported here (it starts NiceGUI), so read it as text."""

    def setUp(self):
        self.text = (PROJECT / "app.py").read_text(encoding="utf-8")

    def test_freeze_support_comes_first_in_the_main_guard(self):
        # Comment lines may sit between the guard and the call; no other line may.
        self.assertTrue(re.search(r'(?m)^if __name__ in \{"__main__", "__mp_main__"\}:\n(?:    #.*\n)*    freeze_support\(\)',
                                  self.text), "freeze_support() must be the first statement under the main guard")

    def test_from_source_the_port_stays_8080(self):
        self.assertTrue(re.search(r"(?m)^PORT = 8080$", self.text), "PORT must stay 8080")
        self.assertTrue(re.search(r"(?m)^    if not is_bundled\(\):\n        return PORT$", self.text),
                        "start_port() must return PORT when not bundled")

    def test_only_the_bundle_opens_the_browser(self):
        line = 'ui.run(host=HOST, port=port, title="RS3 Planner", dark=True, reload=False, show=is_bundled())'
        self.assertTrue(re.search(r"(?m)^ +" + re.escape(line), self.text),
                        "ui.run must use the chosen port and open the browser only in a bundle")

    def test_locks_follow_the_chosen_port(self):
        self.assertTrue(re.search(r"(?m)^        switch_on_locks\(port\)$", self.text),
                        "the locks must be switched on with the chosen port")


if __name__ == "__main__":
    unittest.main()
