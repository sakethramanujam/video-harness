# Changelog

## 0.1.6

- **Edition from the live binary.** A leftover App Store Lite *container* no longer forces `lite-mas` after you switch to website 21.1. Config and Lua RPC follow real `$HOME/.config/video-harness` on desktop.

## 0.1.5

- **`apply_lut` empty path clears the node.** Film Looks print cubes (3513DI / 2383) on Rec.709 DJI are the wrong transform and look dead. Native Rec.709 unless the clip is actually log.

## 0.1.4

- **Overlay titles and LUTs.** Lua/MCP `overlay_fusion_title` (Fusion Text+ on a clip, for titles *over* establishing shots) and `apply_lut` (`TimelineItem.SetLUT`). Follows Joris Hermans’ Resolve 19 cinematic walkthrough (wide establishes, then closer shots; titles over picture).
- Cinematic assembly still cannot blade/ripple or stamp Cross Dissolve on Lite 21.0.4.5.

## 0.1.3

- **Edit dress.** Lua/MCP `set_timecode`, `add_transition` (Cross Dissolve when Resolve exposes `TimelineItem.AddTransition`), `set_item_property` (Zoom/Opacity/Pan), and `insert_title` with optional playhead + Fusion `StyledText`.
- 21.0.4.5 Lite may skip `AddTransition` (added in 21.1). Titles still insert via `InsertFusionTitleIntoTimeline`.

## 0.2.0 (unreleased)

Visual context awareness, Apple Metal memory controls, and automated draft cut generation.

- **Vision & Temporal Compaction.** Fast difference perceptual hash (`dHash`) with Hamming distance comparisons collapses visually static frames across time by 80-90%.
- **Metal Memory Capping & macOS Mach Monitoring.** Mach task info tracks true physical footprint (`phys_footprint`); MLX cache and memory limits configured to prevent evicting Resolve from unified RAM.
- **Compact Sidecar Database.** Compact JSONL sidecar under `~/.config/video-harness/describe/<media_id>.jsonl` enables sub-millisecond search without overloading Resolve's Lua file-bridge.
- **Marker Types.** Added `scene.cut` (Sky) and `visual.shot` (Mint).
- **Automated Draft Cut & Feedback Loop.** `timeline_draft_cut` supports style presets (`montage`, `talking_head_highlights`, `fast_paced_social`) and returns targeted iteration prompts to refine the cut.

## 0.1.2

- **License.** MIT (Copyright 2026 Saketha Ramanjam). `LICENSE` at repo root; `pyproject.toml` declares it.
- **Attributions.** [docs/attributions.md](docs/attributions.md) cites Blackmagic Design (Resolve/Fusion scripting), MCP and the Python SDK, Pydantic, PyYAML, pytest, Jekyll / just-the-docs, GitHub Pages Actions, Srinivasan’s *Samurai Engineer* mapping, Krawetz dHash, Hamming, ISO BMFF, and trademarks we name but do not own.

## 0.1.1

Lua bridge reliability after a real idaho import/place/color on App Store Lite.

- **Clip colors.** Timeline `SetClipColor` names only (Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate). Marker names Cyan/Mint/Red map to Teal/Lime/Violet. Invalid names fail immediately.
- **Inspect JSON.** Lua escapes control characters; the client parses with `strict=False` instead of spinning until timeout. `inspect media=none` skips the bin dump.
- **Serial RPC.** File-queue clients take a thread + `fcntl` lock so parallel MCP calls wait instead of clobbering `request.json`.
- **Stale script.** Heartbeat advertises `methods`. CLI 0.1.1 refuses a running Lua that does not list `set_clip_color` — re-click Utility after `install-bridge`.
- **Scripts menu.** Install copies Lua to **Utility** only. `install-bridge` deletes stray copies from Edit/Comp (those folders *are* the Scripts submenus).
- **Do not** launch `fuscript` from a terminal on Lite — it is not in Resolve’s sandbox and SIGTRAPs.

## 0.1.0

Initial harness: inspect, import, place, typed markers, Lua file-queue, MCP, Grok wiring, GitHub Pages docs.
