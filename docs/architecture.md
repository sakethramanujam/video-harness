---
layout: default
title: Architecture
nav_order: 3
---

# Architecture

Job-oriented harness, not a 300-tool wrap of every Resolve method.

```
Agent (MCP)  or  CLI
        │
        ▼
   Harness (inspect / import / place / mark)
        │
        ▼
   Session.connect()
        ├─ direct   Studio scriptapp("Resolve")
        ├─ bridge   HTTP 127.0.0.1  (Python in-app script)
        └─ lua      file queue      (Lua in-app script)   ← working path on free
```

## Transports

`connect()` tries **direct → HTTP bridge → Lua file-queue** unless `VIDEO_HARNESS_TRANSPORT` is set (`direct` / `bridge` / `lua`).

### Direct (Studio)

`DaVinciResolveScript.scriptapp("Resolve")` plus macOS LAN-IP fallback. Returns `None` on free.

Python ops live in `src/video_harness/scripts/vh_runtime.py` (stdlib-only so the same file can run inside Resolve).

### HTTP bridge (Python in-app)

`Workspace → Scripts` runs `video_harness_bridge.py`, which serves JSON-RPC on `127.0.0.1:8765` with a token from `bridge.json`. Needs in-app Python. Unused on App Store Lite.

### Lua file-queue (free / Lite)

`fuscript -l Lua` runs `video_harness_bridge.lua` inside Resolve. It cannot open a GUI (UIManager = Studio). It cannot bind HTTP reliably in the sandbox.

IPC:

| Role | Path |
|---|---|
| Token + heartbeat | `<config>/bridge.json`, `<config>/bridge-heartbeat.json` (`methods` + `bridge` version) |
| RPC | `<config>/rpc/request.json` → `response.json` (clients lock; one in flight) |
| Log | `<config>/bridge.log` |

`install-bridge` copies Lua to **Utility** only. Edit/Comp copies hijack those Scripts menus; the installer deletes them. Heartbeat without `methods` means RAM is older than disk — re-click Utility.

`<config>` is:

- App Store Lite: `~/Library/Containers/com.blackmagic-design.DaVinciResolveLite/Data/.config/video-harness`
- Otherwise: `~/.config/video-harness`

Lua `$HOME` in the sandbox **is the container Data folder**, so both sides must use that config dir. `install-bridge` and `config_dir()` detect Lite.

Heartbeat is refreshed while the script loops with `bmd.wait(0.2)` (cooperative; a busy `while` is killed).

## Lua vs Python op coverage

| Op | Lua bridge | Python runtime (Studio / HTTP) |
|---|---|---|
| `ping` / `inspect` | yes | yes |
| `import_media` | yes | yes |
| `ensure_timeline` | yes | yes |
| `place` | yes | yes |
| `marker_upsert` | yes | yes |
| `lift` | no | yes |
| `markers_query` / `markers_clear` | no | yes |
| `clip_metadata_get` / `set` | no | yes |

Client-side `markers_from_metadata` inspects then calls `marker_upsert`, so it can run over Lua.

## Resolve API facts the design depends on

- **Studio** for out-of-process scripting.
- **No razor, trim, nudge, move.** Place = `MediaPool.AppendToTimeline([{clipInfo}])` with `recordFrame`, `trackIndex`, `startFrame` / `endFrame`. Lift = delete (effects on that item are lost).
- **Markers** are the timeline data store: `color`, `name`, `note`, `duration`, hidden `customData` (JSON).
- Clip metadata (`GetMetadata` / `GetThirdPartyMetadata`) lives on **media pool items**, not timeline instances.
- **UIManager** (script windows): Studio only, since 19.1.
- **App Store** Resolve is sandboxed (`DaVinciResolveLite`) and cannot exec Homebrew Python.

## Marker payload

```json
{
  "schema": "video-harness.marker/v1",
  "type": "beat",
  "id": "beat-004",
  "source": "audio.onset",
  "attrs": {}
}
```

Color in the UI comes from `types.yaml`. Upsert is idempotent on `id` (delete by id, then add).

## Layout

```
src/video_harness/
  types.yaml                 type → color / scope / duration
  harness.py                 high-level jobs
  session.py                 transport picker
  bridge_client.py           HTTP + file-queue clients
  mark.py                    sidecar events → upsert dicts
  mcp_server.py
  cli.py
  scripts/
    video_harness_bridge.lua headless in-app listener
    bridge.py                HTTP in-app listener
    vh_runtime.py            stdlib Resolve ops
```
