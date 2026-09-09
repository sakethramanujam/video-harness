---
layout: default
title: Grok
nav_order: 5
---

# Use video-harness from Grok

Grok talks to Resolve through this MCP. Resolve must already be running with the Lua bridge clicked **once**.

## 1. Start Resolve

1. Open DaVinci Resolve and a project.
2. **Workspace → Scripts → Utility → video_harness_bridge** (once). No window.
3. In a terminal:

```bash
cd /path/to/video-harness
source .venv/bin/activate
video-harness doctor
```

You want `"bridge": { "ok": true }`.

## 2. Register the MCP in Grok

From this repo:

```bash
grok mcp add --scope project video-harness -- .venv/bin/video-harness mcp
```

That writes `.grok/config.toml`. For every Grok session (any cwd):

```bash
grok mcp add video-harness -- "$(pwd)/.venv/bin/video-harness" mcp
```

Check:

```bash
grok mcp list
grok mcp doctor video-harness
```

In the TUI, `/mcps` should show `video-harness`. Restart Grok (or `/mcps` enable) after adding. Tools show up as `video-harness__inspect`, `video-harness__media_import`, etc.

## 3. Ask Grok

Stay in this repo (project MCP) or have the user-scope server enabled. Then, for example:

> Import `/Users/you/Movies/DaVinci Resolve/Proxy` into the current bin, create timeline `Proxy_Cut` if needed, place the clips on V1 in order, and color-code them: interviews Green, b-roll Blue, and a Cyan `beat` marker at 01:00:02:12.

What Grok should call:

1. `doctor` / `inspect` — project, bin, timelines
2. `media_import` — folder or file paths (absolute; prefer `~/Movies/...` on App Store Lite)
3. `timeline_ensure` — e.g. `Proxy_Cut`
4. `timeline_place` or `timeline_assemble` — put clips on the sequence
5. Color:
   - **Clip colors** (blocks on the timeline): `clip_set_color` with `color` like `Green` / `Blue` / `Orange` and `clip_name` or `media_id`
   - **Ruler markers** (typed): `marker_upsert` / `markers_from_metadata` using types in `types.yaml` (`beat`=Cyan, `dialogue`=Green, `broll`=Blue, `chapter`=Purple, `qc.flash`=Red, …)

## Color names Resolve accepts

`Blue`, `Cyan`, `Green`, `Yellow`, `Red`, `Pink`, `Purple`, `Orange`, `Apricot`, `Brown`, `Fuchsia`, `Rose`, `Lavender`, `Sky`, `Mint`, `Lemon`, `Sand`, `Cocoa`, `Cream`, `White`.

## Each session

Resolve up → click the Lua script once → Grok session in this repo (or with user MCP) → prompt. Do not re-click the script unless `doctor` says the bridge is down.
