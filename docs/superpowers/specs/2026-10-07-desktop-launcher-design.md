# Design: start the app without a terminal (Linux)

2026-10-07 · approved in chat, part by part

## Goal

Open the RS3 Planner without typing anything in a terminal. The app starts quietly
in the background at login, and an **RS3 Planner** icon in the app grid (or dock)
opens it in the browser. This comes before the Tailscale (iPhone) work, which needs
the app to be running whenever the PC is on, not only after a terminal command.

The app itself does not change: same screens, same once-per-run fetch, Refresh as
now, listening on 127.0.0.1 only. Starting it from a terminal keeps working.

## Decisions (made with Chris on 2026-10-07)

| Question | Decision |
|---|---|
| Icon, background service, or both? | **Both.** A systemd *user service* runs the app; a desktop launcher (icon) opens it. |
| When does the app start? | **At login**, automatically. It stops at logout (no `loginctl enable-linger` unless asked). |
| Stats go stale while the app runs for days. Auto-refresh? | **No.** Keep the app as it is: one fetch per app run plus **Refresh**. Home already shows "Stats updated HH:MM, D Mon" beside Refresh. |
| How are the files installed? | **An install script** in the project, `tools/install_desktop.py`, run once by Chris. `--remove` undoes it. |
| Icon | **Lucide's crossed swords in parchment (#F0E8D6) on a forest panel (#16241B, border #2E4636)**, from the icon already bundled in `static/icons/swords.svg` (ISC licence). |

### Facts checked (read-only, 2026-10-07)

- The PC runs Ubuntu 26.04 with GNOME on Wayland. `systemd --user` is available (systemd 259).
  It reports "degraded" only because an unrelated `ydotool.service` failed; that does not affect this.
- `xdg-open`, `gtk-launch` and `notify-send` are installed.
- The app finds its data by its own location (`Path(__file__).parent` in `players.py` and
  `check_methods.py`), so it runs correctly whatever folder it is started from.
- The app fetches the remembered player once at start-up (`fetch_current_on_startup` in `app.py`).
  If the network is not up yet at login, that fetch fails safely: Home shows "No stats loaded"
  with the reason, and **Refresh** fixes it.
- Chris's account can read its own service logs without sudo (`journalctl --user`). Ubuntu's own
  messages ("Failed with result 'exit-code'") are mixed in with the app's, so the service tags
  the app's output with its own name (see part 2) to tell them apart.
- No tool for turning SVG into PNG (`rsvg-convert`, `inkscape`, ImageMagick) is installed. GNOME
  launchers accept SVG icons, so this does not matter here; the iPhone icon (PNG) is solved later.

## 1. What Chris gets and how it behaves

**After the one-time install:**

- The app starts in the background at every login, as the user service `rs3-planner`
  (belongs to Chris's account only; no sudo).
- An **RS3 Planner** icon appears in the app grid; it can be pinned to the dock.

**Clicking the icon** (`tools/open_planner.py` with no option):

1. If the app already answers at `http://127.0.0.1:8080`, open that address in the default
   browser. (Whatever is answering, the service or a copy started from a terminal.)
2. Otherwise run `systemctl --user start rs3-planner`, then check every half second, for up
   to 20 seconds, whether the app answers. As soon as it does, open the browser.
3. If it never answers: no browser. A desktop notification instead:
   - title "RS3 Planner didn't start"
   - body: up to the last 3 lines the app itself printed (from the log, see part 2), then
     "Full log: journalctl --user -u rs3-planner"
   - if the log can't be read or has no app lines, the body is only the "Full log" line.

**Right-click actions on the icon:**

- **Restart RS3 Planner** (`--restart`): `systemctl --user restart rs3-planner`, wait for the
  app as in step 2, then open the browser (or the same "didn't start" notification). Use it
  after editing `data/methods.json` (read only at start-up). Every start also fetches fresh stats.
- **Stop RS3 Planner** (`--stop`): `systemctl --user stop rs3-planner`, then the notification
  "RS3 Planner stopped. Click its icon to start it again." It stays stopped until the icon is
  clicked or the next login.

**Unchanged:**

- `app.py`, every screen, the data files, the fetch rules, 127.0.0.1 only.
- `.venv/bin/python app.py` from a terminal still works. If the background app is already
  running, the terminal copy can't use port 8080 and stops with an "address already in use"
  error; the README says to choose **Stop** on the icon first.

**Crashes:** the service restarts the app 5 seconds after a crash. If it fails 3 times
within 60 seconds (for example, a broken data file makes it exit at once), Ubuntu stops
retrying; the icon's notification then shows why.

**Platforms:** Linux with systemd and a freedesktop desktop (GNOME, KDE, …) only. On Mac and
Windows, the README's terminal steps stay the way to run it.

## 2. Files, install, errors, tests

### New files

| File | What it does |
|---|---|
| `static/icons/app-icon.svg` | The launcher icon: Lucide's swords (parchment) on a rounded forest square with the panel border. Keeps Lucide's licence comment. |
| `tools/open_planner.py` | What the icon runs: open (default), `--restart`, `--stop`. Standard library only. |
| `tools/install_desktop.py` | The installer: install (default), `--remove`, `--show` (print the two files, write nothing). Standard library only. |
| `tests/test_install_desktop.py` | Tests for the installer. |
| `tests/test_open_planner.py` | Tests for the opener. |

`tools/open_planner.py` must not import `app.py` (that would start loading NiceGUI and the
data files). It keeps its own `HOST = "127.0.0.1"` and `PORT = 8080`, commented "must match
app.py"; a test reads `app.py` as text and fails if the two ever differ.

### What the installer writes

Only inside the home folder (no sudo, nothing system-wide). Paths are absolute and point at
the project folder the installer is run from.

**`~/.config/systemd/user/rs3-planner.service`**, a commented unit:

```ini
[Unit]
Description=RS3 Planner (browser app on http://127.0.0.1:8080)
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
WorkingDirectory=<project>
ExecStart="<project>/.venv/bin/python" "<project>/app.py"
Environment=PYTHONUNBUFFERED=1
SyslogIdentifier=rs3-planner
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

- `PYTHONUNBUFFERED=1` makes the app's messages reach the log straight away.
- `SyslogIdentifier=rs3-planner` tags the app's own output, so the opener can read just those
  lines with `journalctl --user -t rs3-planner` and skip Ubuntu's messages.
- `WantedBy=default.target` is what "start at login" means for a user service.

**`~/.local/share/applications/rs3-planner.desktop`**, a launcher with:
`Name=RS3 Planner`, a one-line `Comment`, `Icon=<project>/static/icons/app-icon.svg`,
`Exec=` the venv's Python running `tools/open_planner.py`, `Terminal=false`,
`Categories=Game;`, and two actions, **Restart RS3 Planner** (`--restart`) and
**Stop RS3 Planner** (`--stop`).

**Quoting.** Each file type has its own rules for paths with spaces or special characters.
In `.desktop` `Exec` lines, every argument is wrapped in double quotes, with `"`, `` ` ``, `$`
and `\` escaped by a backslash, and a literal `%` written as `%%`. In the systemd `ExecStart`
line, each path is wrapped in double quotes, with `"` and `\` escaped by a backslash and `%`
written as `%%`. `WorkingDirectory`, `Icon` and the other plain-value lines take the path as
written. The installer refuses a project path containing a newline.

**After writing**, the installer runs:

1. `systemctl --user daemon-reload` (reread the settings)
2. `systemctl --user enable --now rs3-planner` (start it now, and at every login)

and prints what it wrote, whether the app now answers, and how to undo it.

### Installer checks and messages

- **No `.venv`:** if `<project>/.venv/bin/python` is missing, it writes nothing and says to do
  the README's one-time setup first.
- **Already installed:** a file with identical contents is left alone ("already up to date").
  A file with different contents (for example, from the project's old folder) is replaced, and
  it says so.
- **`systemctl` fails:** it shows the command and its error message, says the files were
  written, and stops. It does not try anything else.
- **`--remove`:** runs `systemctl --user disable --now rs3-planner` (no error if it isn't
  installed), deletes the two files if present, runs `daemon-reload`, and says what it removed.
  It never touches `data/`.
- **`--show`:** prints both files' contents and where they would go. It writes and runs nothing.

### Opener details

- "The app answers" means an HTTP request to `http://127.0.0.1:8080/` gets any reply within
  2 seconds. Any status code counts (the home page redirects to `/player` when no player is
  chosen); a refused connection or a timeout doesn't.
- The browser is opened with `xdg-open http://127.0.0.1:8080`.
- Notifications use `notify-send`. If `notify-send` itself is missing or fails, the opener
  prints the same message and exits, without crashing.
- The opener's steps (does it answer, run `systemctl`, read the log, notify, open the
  browser, wait) are small separate functions, so the tests can swap in fakes.

### README

A new section, **"Start it without a terminal (Linux)"**, under *Install*, written for a beginner:

- what the install does (background app at login, an icon) and the one command to run it
- clicking the icon; **Restart** after editing `data/methods.json`; **Stop**
- the stopped-at-logout note
- where the log is: `journalctl --user -u rs3-planner`
- "address already in use" from the terminal: **Stop** on the icon first
- how to remove it (`python3 tools/install_desktop.py --remove`)
- if the project folder moves: run the install again from the new folder

The "Good to know" line about 127.0.0.1 stays true and is unchanged.

### Tests

Standard library only; never touch the real home folder, never run `systemctl`,
`journalctl`, `notify-send` or `xdg-open`, never use the network.

**Installer:**

- the service and launcher texts for a plain project path contain the expected lines
- a project path with spaces (and one with `%`, `"` and `$`) is quoted correctly in both files
- install writes exactly the two files into a scratch home folder and calls `daemon-reload`
  then `enable --now` (recorded by a fake runner)
- a second install with identical files reports "already up to date"; a changed file is
  replaced and reported
- no `.venv/bin/python`: nothing is written and nothing is run
- a project path containing a newline is refused
- a failing fake `systemctl` stops the install with its message
- `--remove` deletes both files and calls `disable --now` then `daemon-reload`; with nothing
  installed it still finishes cleanly
- `--show` writes nothing and runs nothing

**Opener:**

- `HOST` and `PORT` match the values in `app.py`
- already answering: opens the browser; `systemctl` is never called
- not answering, then answering after a few checks: starts the service, then opens the browser
- never answering within 20 seconds: no browser; the notification shows the app's last log
  lines, or only the "Full log" line when there are none (the clock is faked, so the test is
  instant)
- `--restart` calls `restart`; `--stop` calls `stop` and shows the stopped notification
- a missing `notify-send` doesn't crash

### Verification

1. All tests pass (the 146 existing plus the new ones); `python3 check_methods.py` is still clean.
2. `python3 tools/install_desktop.py --show` for the real project folder, shown to Chris
   before he installs.
3. **Chris** runs the install. Then, read-only: `systemctl --user is-active rs3-planner`,
   `ss -ltn` shows the app on `127.0.0.1:8080` only, and the Home page loads.
4. Chris clicks the icon and tries Restart and Stop (or, with his OK, Claude clicks it using
   desktop control).
5. A live failure test that can't touch Chris's service or data: a throwaway project copy in
   the scratch folder (`.superpowers/sdd/desktop-launcher/`) with a broken `methods.json` and
   port 8091, run as a temporary service named `rs3-planner-test` (`systemd-run --user`,
   which leaves nothing behind once it stops). A small scratch script calls the opener with
   its service name, port and log tag pointed at that test service, and the "didn't start"
   notification must appear with the broken file's message. The copy is deleted afterwards.
   So that this works without special options, the opener keeps the service name, port and
   log tag as constants at the top of the file.

While the service holds port 8080, Claude's own test copies use port 8091 (as before), and
Claude stops nothing of Chris's without saying so first.

## Out of scope

- Any change to `app.py` or the screens, including auto-refresh of stale stats.
- Keeping the app running after logout (`loginctl enable-linger`).
- Mac (launchd) and Windows (Task Scheduler) equivalents.
- The Tailscale / iPhone work, which comes next and builds on this.
