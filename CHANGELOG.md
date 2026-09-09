# Changelog

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
