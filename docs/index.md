---
layout: home
title: Home
nav_order: 1
description: DaVinci Resolve harness and MCP for inspect, import, place, and typed markers.
---

# video-harness

DaVinci Resolve harness and MCP server for **timeline placement**, **folder import**, **clip color**, and **typed metadata markers**.

It does not wrap the whole Resolve API. Agents get a small job surface: inspect, import, place, color, mark. Release **0.1.2**: [changelog](https://github.com/sakethramanujam/video-harness/blob/main/CHANGELOG.md). [MIT](https://github.com/sakethramanujam/video-harness/blob/main/LICENSE). [Attributions](attributions.md).

## Docs

| Page | Contents |
|---|---|
| [Setup](setup.md) | Install, which Resolve you have, start the Lua bridge |
| [Architecture](architecture.md) | Transports (Studio / HTTP / Lua file-queue), API limits |
| [MCP and agents](mcp.md) | MCP tools, client config, agent prompts |
| [Grok](grok.md) | Wire this MCP into Grok and prompt import / place / color |
| [Workflows](workflows.md) | Import folders, place clips, proxies, marker types |
| [Troubleshooting](troubleshooting.md) | Doctor output, Scripts menu, sandbox, limitation dialog |
| [License and attributions](attributions.md) | MIT, Blackmagic, MCP, dHash, persona sources |

## Quick start (free Resolve)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
video-harness install-bridge
video-harness doctor
```

1. Open Resolve and a project.
2. **Workspace → Scripts → Utility → video_harness_bridge** (click **once**). No window — that is expected.
3. `video-harness doctor` → `"bridge": { "ok": true }` with `bridge: "0.1.1"` and `set_clip_color` in `methods`.
4. `video-harness inspect`. After `install-bridge`, click Utility again so the running script matches disk.

App Store (“Lite”) vs website install: see [Setup](setup.md). Lite is sandboxed; the website free build is the better $0 option.

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

In Grok: `/mcps` → add or enable `video-harness`. Full tool list: [MCP and agents](mcp.md). Using Grok day to day: [Grok](grok.md).

## What Resolve will not do through this API

- Razor, trim, nudge, or move an existing timeline item (place is append-at-frame; lift is delete).
- Script GUIs (UIManager) on free, since 19.1.
- Out-of-process scripting on free.
- `LinkProxyMedia` is not exposed yet — importing a proxy folder edits those files as sources.

## Source

[github.com/sakethramanujam/video-harness](https://github.com/sakethramanujam/video-harness) · [MIT License](https://github.com/sakethramanujam/video-harness/blob/main/LICENSE) · [Attributions](attributions.md)
