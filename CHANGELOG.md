# Changelog

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
