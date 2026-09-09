# Workflows

## Import media from a folder

`MediaPool.ImportMedia` accepts a list of **files or directories**.

Agent: `media_import` with `paths: ["/abs/folder"]` or a list of files.

CLI/MCP will return imported clips (`name`, `media_id`, `path` once the Lua inspect fix is loaded — re-click the bridge after `install-bridge`).

The current bin is wherever the Media Pool selection is (`inspect` → `media.current_folder`). Switch bins in the UI first, or stay in Master.

App Store Lite may not see arbitrary volumes. Prefer paths under `~/Movies` (Resolve already uses `~/Movies/DaVinci Resolve`).

## Create a timeline and put clips on it

There is no timeline until `timeline_count > 0`. Placement fails without a current timeline.

```
timeline_ensure("Rough_v1")
timeline_place([
  {"media_id": "…", "track_type": "video", "track_index": 1, "record_frame": 86400, "source_in": 0, "source_out": 240}
])
```

Or one call:

```
timeline_assemble(timeline="Rough_v1", paths=["/abs/folder"])
```

That imports, ensures the timeline, then appends every imported clip on V1 in order.

`timeline_place` fields:

| Field | Meaning |
|---|---|
| `media_id` / `clip_name` / `path` | How to find the pool item |
| `track_type` | `video` (default), `audio`, `subtitle` |
| `track_index` | 1-based; extra tracks are added if needed |
| `record_frame` | Timeline destination (subframe allowed). Omit to append at end |
| `source_in` / `source_out` | Source frames (`startFrame` / `endFrame`) |
| `media_type` | `1` video only, `2` audio only |

Resolve **cannot** razor, trim, or move an item already on the timeline. Changing position means lift + place; grades/Fusion on the old item are lost. `timeline_lift` is implemented only on the Python runtime.

## Proxy media

Two different jobs:

**A. Edit the proxy files as the source** (supported)

Import the proxy folder and assemble a timeline from those clips. Delivery later is a recut/relink problem, not this harness.

**B. Camera originals in the pool, proxies linked** (not exposed yet)

Resolve API: `MediaPoolItem.LinkProxyMedia(proxyPath)` / `UnlinkProxyMedia()`. No MCP tool yet. Do not ask the agent to “set proxy mode” — it cannot.

Matching convention if/when that tool exists: same stem, e.g. `A001C001.mov` ↔ `A001C001_proxy.mov`.

## Typed markers

Registry: `src/video_harness/types.yaml` (override with `VIDEO_HARNESS_TYPES`).

| Type | Color | Scope | Duration |
|---|---|---|---|
| `beat` | Cyan | timeline | point |
| `dialogue` | Green | item | range |
| `broll` | Blue | timeline | range |
| `chapter` | Purple | timeline | point |
| `qc.flash` | Red | timeline | point |
| `qc.audio` | Orange | item | range |
| `keyword` | Yellow | clip | range |

Scopes:

- **timeline** — sequence (chapters, beats)
- **item** — this use of a clip on the timeline (`unique_id` required)
- **clip** — media pool item (survives recuts)

`customData` is JSON `video-harness.marker/v1`. Color is what you see in Resolve.

Sidecar → markers:

```json
[
  {"type": "beat", "id": "beat-004", "at": "01:00:02:12", "source": "audio.onset"},
  {"type": "dialogue", "id": "dlg-12", "at": 48, "duration_frames": 36, "media_id": "…"}
]
```

`at` is a timecode (`HH:MM:SS:FF`) or a frame number. Timeline timecode `01:00:00:00` at 24fps is frame `86400`.

`markers_from_metadata(..., from_clips=true)` also maps pool fields (Keywords, Comments, Shot, Scene, Good Take) onto `keyword` / `chapter` clip markers.
