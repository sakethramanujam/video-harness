# Setup

## Requirements

- Python 3.10+ for the CLI / MCP process (the venv can be 3.14).
- DaVinci Resolve **running**, with a **project open**.
- macOS, Windows, or Linux.

## Which Resolve you have

This matters more than the rest of the install.

| Check | Website free | App Store free (“Lite”) | Studio |
|---|---|---|---|
| Bundle ID (macOS) | `com.blackmagic-design.DaVinciResolve` | `com.blackmagic-design.DaVinciResolveLite` | `com.blackmagic-design.DaVinciResolve` |
| `_MASReceipt` | absent | present | absent |
| `doctor` `resolve_edition` | `desktop` | `lite-mas` | `desktop` |
| External `scriptapp` | no (free) | no | yes, if External scripting = Local |
| Workspace → Scripts | yes | sandboxed; scripts live in the container | yes |
| Python in-app scripts | if Resolve can see Python 3 | blocked (`Operation not permitted`) | yes |
| Lua in-app scripts | yes | yes (no UIManager GUI) | yes |

Confirm:

```bash
defaults read "/Applications/DaVinci Resolve.app/Contents/Info" CFBundleIdentifier
ls "/Applications/DaVinci Resolve.app/Contents/_MASReceipt"
```

App Store Lite is sandboxed. User scripts must sit under:

`~/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Fusion/Scripts/`

`video-harness install-bridge` copies into that tree when it exists. The website installer is still the better free build: not sandboxed, same $0 license.

## Install the harness

```bash
cd video-harness
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
video-harness doctor
```

## Free edition: in-app bridge

External processes cannot call `scriptapp("Resolve")` on free Resolve (gated ~19.1). The harness starts a **Lua** script *inside* Resolve. That script polls a JSON file queue the CLI/MCP write to.

```bash
video-harness install-bridge
```

Then:

1. Open DaVinci Resolve and a project.
2. **Workspace → Scripts → Utility → video_harness_bridge** (or **Edit → video_harness_bridge**). Click **once**.
3. No window. No “limitation” dialog. That is expected (see below).
4. `video-harness doctor` — you want `"bridge": { "ok": true, "transport": "lua-file" }`.

Do not click the script again unless `doctor` says the bridge is down. Extra copies race on the same RPC files.

### Python scripts (optional)

`.py` files only appear in Scripts if Resolve can exec Python 3. On macOS it looks at **`PYTHON3HOME` or `/usr/local/bin/python3`**, not Homebrew on `PATH`.

```bash
video-harness enable-python
# if it prints sudo_symlink, run that command
# Cmd+Q Resolve, reopen
```

On App Store Lite, even a correct `python3` is **`Operation not permitted`**. Use the Lua script.

### “You have reached a limitation with DaVinci Resolve”

Since Resolve **19.1**, **UIManager script GUIs are Studio-only**. A script that opens a Fusion window triggers that dialog on free. The shipped Lua bridge is **headless** on purpose. Open **Workspace → Console** if you want the `bridge is RUNNING` prints.

## Studio

**Preferences → General → External scripting using → Local.**

`doctor` should show `scriptapp.connected: true`. The MCP then uses fusionscript directly; the Lua bridge is optional.

## Reload the bridge after code updates

`install-bridge` updates files on disk. A script already running still has the old Lua in memory. Click the script once more (after stopping extras if `doctor` shows several `fuscript` PIDs).
