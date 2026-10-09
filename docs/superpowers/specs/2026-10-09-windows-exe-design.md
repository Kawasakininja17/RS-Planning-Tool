# Design: a Windows app for the clan

2026-10-09 · approved in chat, part by part

## Goal

Share the RS3 Planner with Chris's clan, who use Windows: a zip they extract and a
program they double-click, with no Python and no project setup. Chris stays on Linux
with the background service and the swords icon, which keep working exactly as they do.

A Windows program can only be built on Windows, so GitHub's free Windows build machines
do the building. Everything that can be proved on Linux is proved first, with a Linux
build of the same app used purely as a rehearsal. One clan member does a single
hands-on check on a real Windows PC before anyone else gets it.

The app itself does not change: same screens, same once-per-run fetch plus Refresh,
listening on 127.0.0.1 only, same host lock. Only where a bundled copy saves its
data, which port it uses and how it opens are new, and only when it runs as a bundle.

## Decisions (made with Chris on 2026-10-09)

| Question | Decision |
|---|---|
| Who is it for, which computer? | **The clan, on Windows.** A Linux build is made first as a rehearsal only; Chris keeps the service. |
| Where is the Windows build made? | **GitHub Actions**, on a GitHub-hosted Windows machine; one clan member does the hands-on check. |
| Browser tab or its own window? | **Browser tab.** A console window shows the app is running; closing it stops the app. Native window maybe later. |
| One file or one folder? | **One folder, shared as a zip.** One file maybe later (one build option). |
| Where does a bundle save player data? | **The standard per-user folder:** `%LOCALAPPDATA%\RS3 Planner` on Windows, `$XDG_DATA_HOME/rs3-planner` (default `~/.local/share/rs3-planner`) on Linux. |
| Copy Chris's existing `data/players/`? | **No. A bundle starts fresh**; there is no import feature. |
| Port | **8095 preferred.** If it already answers as RS3 Planner, open that and exit; if another program has it, pick a free port. |
| Updates | **A new build per update**, with a version line (build date + short commit) printed at start-up. |
| Name and icon | **"RS3 Planner"**, with the crossed swords from `static/icons/app-icon.svg` as a `.ico`. |
| Unsigned-program warning | **Unsigned, with a plain heads-up** in `Start here.txt` and in Chris's message to the clan. |
| Where the zip lives | **GitHub Releases**, the first one marked pre-release for the clan check. Every publish only on Chris's yes. |
| Terminal scripts | **Unchanged**, not shipped as programs. The zip holds the browser app only. |
| Build tool | **`nicegui-pack`** (NiceGUI's own, built on PyInstaller), run by one build script used on both systems. |
| Making the `.ico` | **GNOME's SVG converter**, installed by Chris with one `sudo apt` line, run once; the PNG and `.ico` are committed. |

### Facts checked (2026-10-09, official pages read as page text in the built-in browser)

- **PyInstaller 6.22.3, "Using PyInstaller" → "Supporting Multiple Operating Systems":** a bundle
  must be made separately on each operating system ("you must install PyInstaller on each platform
  and bundle your app separately on each"). A Windows `.exe` cannot be built on Linux.
- **PyInstaller on PyPI (6.22.3):** supports Python 3.8–3.15 (Chris has 3.14).
- **PyInstaller "Requirements":** a Linux build needs `ldd`, `objdump` and `objcopy`. All three are
  on Chris's PC (binutils 2.46, checked read-only).
- **PyInstaller "What PyInstaller Does and How It Does It":** a one-file program unpacks into a new
  `_MEIxxxxxx` temporary folder on every start and deletes it at exit, so nothing saved inside the
  bundle survives; the folder is left behind if the program is killed. The page advises getting the
  app working as one folder before trying one file, as that is "much easier to diagnose".
- **PyInstaller "Run-time Information":** a bundle has `sys.frozen` set and `sys._MEIPASS` holding the
  bundle folder; for one folder that is the `_internal` folder. Each module's `__file__` points inside
  that folder (`sys._MEIPASS + 'module.py'`). So `check_methods.DATA_DIR` and `app.HERE` keep working
  unchanged, as long as the build places the data files at `_internal/data/` and `static/` at
  `_internal/static/`.
- **PyInstaller "Using PyInstaller", options:** `--icon` takes a `.ico` for Windows, or another image
  that Pillow converts if installed. `--name` names the program. One-folder builds put every supporting
  file into one contents folder beside the program.
- **Pillow 12.3.0, "Image file formats":** no SVG support. It can save an ICO; default sizes 16 to 256
  pixels, larger than the original ignored. So the SVG must be turned into a 256×256 PNG first.
- **NiceGUI, "Configuration & Deployment" → "Package for Installation":** `nicegui-pack` builds on
  PyInstaller and needs `ui.run(..., reload=False)` plus at least one `@ui.page` (the app has both).
  `--windowed` is only for native mode (in browser mode it leaves no way to stop the app). Install
  PyInstaller in the same venv as NiceGUI.
- **NiceGUI, "Packaging with Native Mode":** when packaging, call `freeze_support()` as the first
  statement in the main guard, "to prevent new processes from being spawned in an endless loop".
  The section is headed for native mode. It applies here too because NiceGUI sets up a process pool
  at every start (`run.setup()` in `nicegui/run.py`, read in the venv). To be confirmed against
  PyInstaller's own multiprocessing notes when the plan is written.
- **NiceGUI "Native Mode":** a native window needs pywebview, .NET and Microsoft's WebView2 Runtime on
  Windows, and GTK or Qt on Linux. Not used (browser tab decided).
- **`nicegui-pack`'s own source** (`.venv/.../nicegui/scripts/pack.py`, NiceGUI 3.17.1): it builds one
  PyInstaller command, always adds NiceGUI's whole package folder as data, adds each `--add-data`
  given, and has `--dry-run`. It runs PyInstaller with `subprocess.call` and **ignores its result**,
  so a failed PyInstaller run still looks like success. The build script must check the output itself.
- **NiceGUI's `ui.run` and helpers** (source, 3.17.1): `show=True` waits until the port answers, then
  opens `http://<host>:<port>/` with Python's `webbrowser.open`. `native.find_open_port()` scans
  8000–8999 by binding to `localhost`.
- **Microsoft "KNOWNFOLDERID":** `FOLDERID_LocalAppData` is per-user, default `%LOCALAPPDATA%`
  (`%USERPROFILE%\AppData\Local`).
- **freedesktop.org "XDG Base Directory Specification":** user data goes under `$XDG_DATA_HOME`, or
  `$HOME/.local/share` when that is unset or empty.
- **GitHub "GitHub Actions billing":** free for public repositories using standard GitHub-hosted
  runners. **"GitHub-hosted runners reference":** standard runners are "free and unlimited on public
  repositories". Windows x64 has 4 CPUs and 16 GB (`windows-latest`, `windows-2025`, `windows-2022`).
- **GitHub "Downloading workflow artifacts":** only people signed in to GitHub with read access can
  download artifacts; they are kept 90 days by default.
- **GitHub "About releases":** releases are tied to git tags; anyone with read access can view them
  (everyone, for a public repo); each file under 2 GiB, no limit on total size or bandwidth.
  Whether downloading needs a sign-in is not stated: the clan check confirms it.
- **Microsoft "SmartScreen overview":** downloaded programs that aren't "well known and downloaded
  frequently" get a warning; reputation is tracked per file and per signing certificate.
  **SmartScreen FAQ:** the warning "is not an indication that the download is malicious", and
  "if your program is not digitally signed, reputation cannot automatically be shared across
  different versions and builds" (so every new version may warn again). The exact wording of the
  warning was not found on an official page; the clan check records it.
- **Microsoft "Artifact Signing" (formerly Trusted Signing) pricing:** Basic $9.99 a month, Premium
  $99.99 a month; individual identity validation needs a government ID and a face check (its FAQ).
  Not used.
- **Microsoft's free Windows test machines:** their old download address now redirects to a general
  page; the Windows 11 Enterprise evaluation (90 days, Microsoft account, "for IT professionals") is
  what remains. Not used (GitHub builds instead).

## 1. Changes inside the app

### `bundle.py` (new, standard library only)

Answers "am I a bundle?" questions in one place, so tests can use it directly (like `host_lock.py`).

- `is_bundled()`: PyInstaller's documented check, `getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")`.
- `user_data_dir()`: the folder for this user's saved data.
  - Windows: `%LOCALAPPDATA%\RS3 Planner`. If `LOCALAPPDATA` is missing or empty, it stops with a plain
    message (no guessing a path).
  - Linux: `$XDG_DATA_HOME/rs3-planner`, or `~/.local/share/rs3-planner` when it is unset or empty.
  - Any other system: a plain "not supported" message.
- `version_text()`: the version line from the bundled version file (`RS3 Planner 2026-10-12 (ea96c3c)`),
  or `None` when running from source.
- `planner_answers(port)`: asks `http://127.0.0.1:<port>/` with no proxy and a 2-second limit, and is
  true only if the page is RS3 Planner (its title). A refused connection, a timeout or another
  program's page are all false.
- The port choice: given the preferred port (8095), returns either "already running" or the port to
  use (8095 if free, otherwise `find_open_port()`). Its outside effects are passed in, so tests use
  fakes.
  *Changed during the Linux rehearsal (2026-10-09):* "free" means nothing answers on 8095
  (`something_answers`, a plain connection attempt). NiceGUI's `find_open_port()` called 8095 busy
  for about a minute after a copy closed (leftover TIME-WAIT connections), so a quick reopen moved
  to 8096. `find_open_port(8096, 8999)` is now used only when another program listens on 8095.

### `players.py`

`PLAYERS_DIR` is `user_data_dir() / "players"` when bundled, and `data/players` (as now) otherwise.
Nothing else changes: every other file reaches player files through `player_dir()`.

### `app.py`

**Run from source: unchanged.** Port 8080, `show=False`, the same two locks, same messages.
`tools/open_planner.py` and its "HOST/PORT match app.py" test stay as they are.

**Run as a bundle, in this order:**

1. `freeze_support()` is the first statement in the main guard.
2. Print the version line and `Your saved data: <folder>`.
3. If 8095 answers as RS3 Planner: print "RS3 Planner is already running", open the browser there,
   and exit. No second fetch and no second writer.
4. Otherwise use 8095 if free; if another program has it, use `find_open_port()` and print which port.
5. Add both locks built from the chosen port. The lock and static-file set-up moves into one
   function called just before `ui.run` (still before it, as NiceGUI requires). From source it is
   called with 8080, so the result is the same as today.
6. `ui.run(host="127.0.0.1", port=<chosen>, title="RS3 Planner", dark=True, reload=False, show=True)`.
7. Print "RS3 Planner is running. Keep this window open; close it to stop the app."

If start-up fails as a bundle (no free port, `LOCALAPPDATA` missing), the message is printed,
followed by "Press Enter to close", so the console window doesn't vanish before it can be read.

Known small gap: if the first copy had to fall back to another port, a second copy won't find it
and starts a second copy. This needs both a port clash and a double start; noted, not handled.

### What does not change

- The rulebook files are read from where they are today (`DATA_DIR`, `HERE`); the bundle puts them
  in matching places.
- `rs3_planner.py`, `plan_session.py` and `tools/` keep working as they do. Run from source, they use
  `data/players/`.
- The app still listens on 127.0.0.1 only, one person per copy, everything offline except RuneMetrics.
- A fresh bundle has no remembered player, so it does not fetch at start-up; it fetches once a player
  is chosen, then once per run, plus Refresh, as now.

## 2. The build and its checks

### Files

- `requirements-build.txt` (new): `nicegui==3.17.1`, `pyinstaller==6.22.3` and a pinned Pillow
  (version chosen from PyPI when the plan is written). Installed only into `.venv-build/`, never into
  `.venv/` (which stays what `requirements.txt` says, for the service) and never system-wide.
- `.gitignore`: adds `build/`, `dist/`, `.venv-build/`.
- `static/icons/app-icon.png` (256×256) and `static/icons/app-icon.ico`: made once from
  `app-icon.svg` with GNOME's SVG converter (Chris installs it with one `sudo apt` line; package name
  confirmed on Ubuntu's package site first), then Pillow saves the `.ico`. Both committed. The build
  itself needs no icon tools.

### `tools/build_exe.py` (new)

One script, run on Chris's PC (from `.venv-build/`) and on GitHub's Windows machine. It stops at the
first failed step and names it.

1. Run the data check (`check_methods.py`); refuse to build broken data.
2. Write the version file: build date and short commit. With uncommitted changes the line says so
   (`(ea96c3c, uncommitted changes)`), so a rehearsal build can't pass for a real one.
3. Run `nicegui-pack --onedir --clean --noconfirm --name "RS3 Planner" --icon static/icons/app-icon.ico`,
   adding exactly: `data/methods.json`, `data/quests.json`, `data/unlocks.json` (to `data/`), `static/`
   (to `static/`) and the version file. It is never given the `data/` folder itself.
4. Check that `dist/RS3 Planner/RS3 Planner` (`.exe` on Windows) exists, and that the three JSON files
   and `static/app.css` are inside (making up for `nicegui-pack` ignoring PyInstaller's result).
5. **The guard.** Write every path in the bundle to `dist/bundle-contents.txt`. Fail if any path
   contains `players`, `current.txt`, `answers.json`, `last_goal` or `snapshots`. Where
   `data/players/` exists (Chris's PC), also search the bytes of every bundled file for each player's
   name (folder form and spaced form); names already present in the git-tracked source are skipped
   (already public). Print **counts only**, never a name.
6. Write `Start here.txt` into the app folder and zip it as `dist/RS3-Planner-<date>.zip`:

```
RS3-Planner-2026-10-12.zip
└── RS3 Planner\
    ├── RS3 Planner.exe        the one to double-click
    ├── Start here.txt         how to start and stop it, where data is kept, the Windows warning
    └── _internal\             support files
```

### `tools/smoke_test_exe.py` (new)

Starts the built app and checks it from outside, on both systems:

- `LOCALAPPDATA` / `XDG_DATA_HOME` point to a scratch folder for the run (nothing real touched; a
  fresh start, so no RuneMetrics fetch).
- The app answers on 8095 with the title "RS3 Planner"; the per-user folder appears in the scratch folder.
- Host lock: a foreign `Origin` gets 403; a foreign `Host` gets 400.
- A second copy prints "already running" and exits.
- The app is stopped at the end.

### `.github/workflows/build-windows.yml` (new)

- Runs only on **Run workflow** (`workflow_dispatch`), never on push.
- Windows machine, Python 3.14, `requirements-build.txt`. Read-only permissions, so it can't publish.
- Steps: the 240+ tests, `tools/build_exe.py`, `tools/smoke_test_exe.py`, then upload the zip and
  `bundle-contents.txt` as an artifact.
- Action versions are taken from their official pages when the plan is written.
- If tests for the Linux-only launcher fail on Windows, work stops and each one is brought to Chris;
  none are skipped quietly.

### Publishing

After a passing run, and only on Chris's yes: a release named `RS3 Planner <date>` (tag
`v<date>`) with the artifact's zip attached. The first is marked **pre-release** for the clan
check, and becomes a normal release after it passes. Chris publishes on GitHub's site, or the
release is prepared with `gh` and run only after Chris approves that specific release.

## 3. Testing and proof

### Automatic tests (tests first; each new file broken on purpose once or twice)

- `bundle.py`: bundle check with fake `sys` values; data folder for Windows (`LOCALAPPDATA` set,
  missing) and Linux (`XDG_DATA_HOME` set, empty, unset); version line (file present, absent);
  `planner_answers` with a fake reply (RS3 Planner page, another program's page, refused); port
  choice (already running, 8095 free, 8095 taken by another program).
- `players.py`: `PLAYERS_DIR` uses the per-user folder only when bundled. No real home folder touched.
- `app.py` text checks (assertTrue/assertFalse with a short message, matched at line starts):
  `freeze_support()` first in the main guard; the source run keeps 8080 and `show=False`; the locks are
  built from the chosen port.
- `build_exe.py`'s guard: fake contents lists with `players/`, `answers.json` etc. fail; a name search
  with "Some Player" reports a count and never prints the name; the version line marks uncommitted changes.
- All existing tests plus the new ones pass; `python3 check_methods.py` passes.

### Nothing changed for Chris

- Frozen before/after of the **source** app on 8091 (`run_frozen.py`, frozen RuneMetrics replies):
  every screen the same except "Stats updated HH:MM" and "N snapshots · last HH:MM".
- Chris's service on 8080: read-only check (`systemctl --user is-active rs3-planner` and one request)
  before and after each step. Never stopped or restarted without asking.

### The bundle matches the source app

A bundle can't be given frozen replies (`run_frozen.py` swaps code before it loads; a bundle's code
is sealed). Instead: run the built Linux app (scratch data folder holding a copy of Chris's player
data) and then the source app, **one after the other on the same port** (8095, so the browser's
stored "before" texts carry over), while the account isn't being played. Each run saves a snapshot.
If the two snapshots' XP is identical, every screen must read the same except the two clock lines.
If XP moved, that attempt doesn't count and is redone. Two RuneMetrics fetches per attempt. The
scratch copies are deleted afterwards.

### Saved data survives

On the built Linux app with a scratch data folder: choose a player (the second public test name,
asked from Chris then, used only live), answer an "I have it", change the goal, close, reopen: all still there.

### Windows

The GitHub run passes (tests, build, smoke test). `bundle-contents.txt` from the artifact is read
and holds no player paths.

### The clan member's check (sent by Chris)

1. Download from the pre-release **without** signing in to GitHub.
2. Note the exact warning Windows shows and which button gets past it.
3. Extract, double-click `RS3 Planner.exe`; the browser opens.
4. Choose a player; a plan shows.
5. Close the black window, reopen: the player is remembered.
6. Double-click twice: only one copy runs.
7. Try opening it from inside the zip without extracting; say what happens.
8. Read out the version line.

### Documentation

- README: "Windows app (for clan members)" (download, extract, the warning, start, stop, where data
  is kept, updating), and a short "Building the Windows app" section for tinkerers.
- `Start here.txt` inside the zip, using the warning's real wording once the clan check records it.

## 4. Order of work

Each step is committed when it works; then work stops for Chris.

1. `bundle.py` and the `players.py` change (tests first).
2. `app.py` start-up changes, plus the source before/after.
3. The icon (Chris's `sudo apt` line).
4. `tools/build_exe.py`, its guard, and `tools/smoke_test_exe.py`.
5. The Linux rehearsal: build, smoke test, screen comparison, saved data surviving.
6. The GitHub workflow (pushing it needs Chris's OK) and its first Windows run.
7. The pre-release (Chris's OK) and the clan check.
8. The real release (Chris's OK), README and `Start here.txt` with the recorded warning wording.

## Out of scope

- A native window (pywebview), one-file builds, code signing: possible later, each a build-option or
  settings change, not a redesign.
- A Mac build.
- Importing existing `data/players/` into a bundle.
- Shipping the terminal scripts or `tools/` as programs.
- Automatic update checks or downloads; methods outside the bundle.
- Building on every push; publishing from the workflow.
- Handling a second copy when the first had to fall back to another port.
