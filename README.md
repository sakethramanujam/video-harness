# video-harness

DaVinci Resolve harness and MCP server for **timeline placement**, **folder import**, **clip color**, and **typed metadata markers**.

It does not wrap the whole Resolve API. Agents get a small job surface: inspect, import, place, color, mark.

Current release: **0.1.4** — [CHANGELOG](CHANGELOG.md). License: [MIT](LICENSE). Attributions: [docs/attributions.md](docs/attributions.md). Agents (any model) read [AGENTS.md](AGENTS.md).

## Docs

Site: **[sakethramanujam.github.io/video-harness](https://sakethramanujam.github.io/video-harness/)**

| Page | Contents |
|---|---|
| [Setup](docs/setup.md) | Install, which Resolve you have, start the Lua bridge |
| [Architecture](docs/architecture.md) | Transports (Studio / HTTP / Lua file-queue), API limits |
| [MCP and agents](docs/mcp.md) | MCP tools, client config, agent prompts |
| [Grok](docs/grok.md) | Wire this MCP into Grok and prompt import / place / color |
| [Workflows](docs/workflows.md) | Import folders, place clips, proxies, marker types |
| [Troubleshooting](docs/troubleshooting.md) | Doctor output, Scripts menu, sandbox, limitation dialog |
| [License and attributions](docs/attributions.md) | MIT license, Blackmagic, MCP, dHash, persona sources |

## Quick start (free Resolve)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
video-harness install-bridge
video-harness doctor
```

1. Open Resolve and a project.
2. **Workspace → Scripts → Utility → video_harness_bridge** (click **once**). No window — that is expected. Do not use Scripts → Edit (that menu is for Edit-page scripts).
3. `video-harness doctor` → `"bridge": { "ok": true, "bridge": "0.1.1" }` and a `methods` list that includes `set_clip_color`.
4. After every `install-bridge`, click Utility **once more** so RAM matches disk. Two `fuscript` PIDs race — stop extras; never start `fuscript` from a shell on App Store Lite.
5. `video-harness inspect` (use MCP `media=none` when you only need the timeline).

App Store (“Lite”) vs website install: see [Setup](docs/setup.md). Lite is sandboxed; the website free build is the better $0 option.

## How it talks to Resolve

```
Agent / CLI  →  Harness  →  Studio scriptapp
                          →  or Lua script inside Resolve (file queue)
```

Free editions cannot be driven from an external `scriptapp`. The Lua script runs from **Workspace → Scripts** and polls JSON under the Resolve config dir (container path on App Store Lite).

## MCP

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

Example: *Import `/Users/you/Movies/DaVinci Resolve/Proxy`, index visual context, and assemble draft cut `Proxy_Cut` in style `montage`.* Color-code with `clip_set_color` (Cyan→Teal, Mint→Lime, Red→Violet; see [workflows](docs/workflows.md)).

### Vision & Edit-Aware Tools
- `clip_describe_start`: Background VideoToolbox + dHash visual context indexing with hard Metal/RAM bounds.
- `clip_describe_status`: Poll progress, segments count, and physical memory footprint.
- `clip_search_visual`: Instant keyword search over compact JSONL sidecar without touching Lua bridge.
- `timeline_draft_cut`: Generate a first-pass edit cut in a specified style (`montage`, `talking_head_highlights`, `fast_paced_social`) and return structured feedback prompts for iteration.


Full tool list and prompts: [MCP and agents](docs/mcp.md).

## What Resolve will not do through this API

- Razor, trim, nudge, or move an existing timeline item (place is append-at-frame; lift is delete).
- Script GUIs (UIManager) on free, since 19.1.
- Out-of-process scripting on free.
- `LinkProxyMedia` is not exposed yet — importing a proxy folder edits those files as sources.

## Layout

```
AGENTS.md                            persona + document-and-commit habit
src/video_harness/
  types.yaml                         marker type → color / scope
  clip_colors.py                     timeline clip colors + aliases
  harness.py                         inspect / import / place / color / mark
  session.py                         direct | HTTP | Lua
  scripts/video_harness_bridge.lua   in-app listener (Utility only)
  scripts/vh_runtime.py              Python Resolve ops (Studio)
  mcp_server.py
```

## License

[MIT](LICENSE) © 2026 Saketha Ramanjam. DaVinci Resolve is a product of Blackmagic Design Pty Ltd; this project is not affiliated with or endorsed by Blackmagic Design. Full citations: [License and attributions](docs/attributions.md).
