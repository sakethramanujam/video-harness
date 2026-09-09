---
layout: default
title: MCP and agents
nav_order: 4
---

# MCP and agents

The MCP server is `video-harness mcp` (stdio). It is a thin wrapper over `Harness`.

## Client config

```json
{
  "mcpServers": {
    "video-harness": {
      "command": "/ABS/PATH/TO/video-harness/.venv/bin/video-harness",
      "args": ["mcp"]
    }
  }
}
```

Use the venv binary so `mcp` / `pydantic` / `pyyaml` resolve. Restart the MCP client after changing this.

Keep Resolve + the Lua bridge running. The MCP process does not start Resolve.

## Tools

| Tool | What it does |
|---|---|
| `doctor` | Paths, `scriptapp`, HTTP bridge, Lua heartbeat |
| `reconnect` | Drop cached session, connect again |
| `inspect` | App, project, current timeline, media pool (`media=current\|all`) |
| `type_registry_get` | Marker types from `types.yaml` |
| `media_import` | `ImportMedia` on file **or folder** paths |
| `timeline_ensure` | Create or switch timeline (idempotent) |
| `timeline_place` | Append clips at track / record frame / source in-out |
| `timeline_lift` | Delete timeline items (Python runtime only) |
| `timeline_assemble` | Import + ensure + place in one call |
| `marker_upsert` | Create/replace typed markers by `payload.id` |
| `markers_query` | Filter markers (Python runtime only) |
| `markers_from_metadata` | Map `{type, at, ...}` events (and optional clip metadata) to upserts |
| `markers_clear` | Delete by id / frame / color (Python runtime only) |
| `clip_metadata_get` | Pool-item metadata (Python runtime only) |

Resources: `resolve://status`, `resolve://timeline`, `resolve://types`.

On the **Lua** transport, tools that are “Python runtime only” fail. Stick to inspect / import / ensure / place / marker_upsert / markers_from_metadata.

## Prompts that work

Read first:

> Check that DaVinci Resolve is connected. Report edition, page, project name, timeline count, and clips in the current bin (name, media_id, path). Do not mutate anything.

Import a folder:

> Import everything in `/Users/you/Movies/DaVinci Resolve/Media/A001` into the current bin. Inspect and list the new media_ids.

Rough cut from proxies:

> Assemble a timeline named `Proxy_Cut` from `/Users/you/Movies/DaVinci Resolve/Proxy`. Place every imported clip on V1 in import order.

Place one clip:

> Place clip `A001C001_proxy.mov` on video track 1 at 01:00:00:00, source frames 0–240.

Mark:

> Add a `chapter` marker at 01:00:00:00 on the current timeline, id `open`, note “cold open”.  
> Stamp these sidecar events as typed markers: `[{"type":"beat","id":"beat-004","at":"01:00:02:12","source":"audio.onset"}]`.

Rules to give the agent (or rely on tool docs):

- Call `inspect` before mutating.
- Prefer `timeline_ensure` over ad-hoc create.
- Pass **absolute** paths Resolve can read (Movies is safest on App Store Lite).
- One running bridge script. Do not tell the user to click Scripts repeatedly.

## CLI equivalents

```bash
video-harness doctor
video-harness types
video-harness inspect
video-harness inspect --media all --transport lua
video-harness mcp
```
