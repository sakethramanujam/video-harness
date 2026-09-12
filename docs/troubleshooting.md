---
layout: default
title: Troubleshooting
nav_order: 7
---

# Troubleshooting

Run `video-harness doctor` first. Read `next`, `resolve_edition`, `scriptapp`, and `bridge`.

## `scriptapp.connected: false`

Normal on free. Use the in-app Lua bridge. Studio: set **Preferences → General → External scripting using → Local**, then `reconnect`.

## `bridge.ok: false` / heartbeat missing

The Lua script is not looping.

- Project must be open.
- **Workspace → Scripts → Utility → video_harness_bridge**, **once**.
- `doctor` `resolve_process.matches` should include `fuscript ... video_harness_bridge.lua`.
- Log: Lite container `Data/.config/video-harness/bridge.log`, else `~/.config/video-harness/bridge.log`.

## Scripts menu has Comp / Edit / Color / Deliver but no script

Those names are **folders**, not your file. The bridge lives in **Utility**.

If the `.lua` file still is not listed:

1. Confirm which app is running (see [Setup](setup.md)).
2. App Store Lite: files must be under the **container** `Fusion/Scripts/...`. `install-bridge` does this when `lite-mas` is detected.
3. Website build: `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/`.
4. `.py` files stay hidden until Resolve can exec Python; Lua should still list.

## Clicking the script does nothing on 21.1

Fusion 21.1 can start Lua with **`package` nil**. The bridge used `package.config` for path separators and died immediately (`attempt to index global 'package'`). Current Lua does not touch `package`. Click Utility again after `install-bridge`.

## Clicking the script does nothing

Headless Lua has **no window**. Open **Workspace → Console** for prints. `doctor` heartbeat `ok: true` means it is running.

Several `fuscript ... video_harness_bridge.lua` PIDs means multiple clicks. They race. Quit extras (or Cmd+Q Resolve) and click **once**.

## Two Resolve apps / idaho missing after “updating”

The App Store app (`/Applications/DaVinci Resolve.app`, Lite) and the website installer (`/Applications/DaVinci Resolve/DaVinci Resolve.app`) are different bundles. The website does not replace the Store app.

Lite projects live in the leftover container `…/Containers/com.blackmagic-design.DaVinciResolveLite/Data/Library/Application Support/Resolve Project Library`. 21.1 uses `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Resolve Project Library`. Copy the `Projects/idaho` folder across (with 21.1 quit) or connect the Lite folder as a disk library in Project Manager.

A leftover Lite **container** is not Lite running. `doctor` `resolve_edition` follows the **live** `Resolve` binary. After removing Lite, click Utility again so Lua writes `~/.config/video-harness/` (real `$HOME`), not the sandbox.

## Two `video_harness_bridge` entries in Scripts

Resolve lists every `.lua` and `.py` it finds in Fusion/Scripts. Duplicates come from:

- **Utility + Edit/Comp** (old installer)
- **User** `~/Library/Application Support/Blackmagic Design/.../Fusion/Scripts/Utility` **and** **system** `/Library/Application Support/.../Fusion/Scripts/Utility`
- **`video_harness_bridge.lua` next to `video_harness_bridge.py`** (same stem; 21.1 shows both once Python is visible)

`install-bridge` now plants **one Lua** in the Utility folder for this edition and deletes the extras. Re-run it, then reopen **Workspace → Scripts**. Click only the Lua **Utility** item, once.

## “You have reached a limitation with DaVinci Resolve”

Free Resolve since **19.1**: **UIManager (script GUI) is Studio-only**. The current Lua bridge does not open a window. If you still see this on the headless script, this build is blocking in-app scripting — use the website free installer or Studio.

## “Python is not installed” / `.py` missing from Scripts

macOS Resolve ignores Homebrew `PATH`. It uses `PYTHON3HOME` or `/usr/local/bin/python3`.

```bash
video-harness enable-python
```

Then Cmd+Q Resolve.

App Store Lite log line:

```
sh: .../python3: Operation not permitted
```

Sandbox. Use Lua.

`$PYTHON3HOME/bin` must contain an unversioned **`python3`**, not only `python3.12`. `enable-python` creates that symlink.

## `inspect` has `timeline_count: 0`

No timeline in the project. Create one in the UI or `timeline_ensure`. You can still import to the media pool.

## Clip entries with no `name` / `path` / `media_id`

Lua omitted nil fields. Fixed on disk; **re-click the bridge** so the running script reloads, then `inspect` again.

## Import from a folder returns nothing

- Absolute path, folder exists.
- Lite sandbox: try `~/Movies/...`.
- Current Media Pool folder is the import target.

## Proxy link did not happen

There is no `LinkProxyMedia` tool yet. Importing proxy files makes **new clips**, it does not attach proxies to camera originals.

## After `install-bridge`, behavior unchanged

Running Lua is the old in-memory copy. Click the script again (only one instance). `doctor` fails fast when the heartbeat has no `methods` list (CLI 0.1.1+). Do **not** start `fuscript` from a terminal on App Store Lite — it is sandboxed and will SIGTRAP (`Process is not in an inherited sandbox`).

## `inspect` hung / “Lua bridge did not answer in time” after a large import

The Lua JSON encoder used to emit raw control characters from clip metadata, and the client spun until timeout. 0.1.1 escapes those characters and parses with `strict=False`. Prefer `inspect` `media=none` when you only need the timeline.

## Parallel MCP calls failed with `request.json.tmp` FileNotFoundError

The Lua queue is one `request.json`. 0.1.1 takes a process+thread lock so concurrent `clip_set_color` / `inspect` calls wait instead of clobbering the file.

## `SetClipColor` returned success false / colors did not stick

Timeline clip colors are **not** marker colors. Cyan, Mint, and Red are invalid. Use Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate. Aliases: Cyan→Teal, Mint→Lime, Red→Violet. The harness maps those aliases before calling Resolve.

## Confirm App Store vs website (macOS)

```bash
defaults read "/Applications/DaVinci Resolve.app/Contents/Info" CFBundleIdentifier
# website: com.blackmagic-design.DaVinciResolve
# store:   com.blackmagic-design.DaVinciResolveLite

ls "/Applications/DaVinci Resolve.app/Contents/_MASReceipt"
# store has receipt
```

Website free download: [blackmagicdesign.com/products/davinciresolve](https://www.blackmagicdesign.com/products/davinciresolve) — not the App Store button. Remove or rename the Store app first or Spotlight will keep launching Lite.
