# video-harness

DaVinci Resolve harness and MCP server for **timeline placement**, **folder import**, and **typed metadata markers**.

It does not wrap the whole Resolve API. Agents get a small job surface: inspect, import, place, mark.

## Docs

| Doc | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Install, which Resolve you have, start the Lua bridge |
| [docs/architecture.md](docs/architecture.md) | Transports (Studio / HTTP / Lua file-queue), API limits |
| [docs/mcp.md](docs/mcp.md) | MCP tools, client config, agent prompts |
| [docs/workflows.md](docs/workflows.md) | Import folders, place clips, proxies, marker types |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Doctor output, Scripts menu, sandbox, limitation dialog |

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
3. `video-harness doctor` → `"bridge": { "ok": true }`.
4. `video-harness inspect`.

App Store (“Lite”) vs website install: see [setup.md](docs/setup.md). Lite is sandboxed; the website free build is the better $0 option.

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

Example: *Import `/Users/you/Movies/DaVinci Resolve/Proxy` and assemble timeline `Proxy_Cut`.*

Full tool list and prompts: [docs/mcp.md](docs/mcp.md).

## What Resolve will not do through this API

- Razor, trim, nudge, or move an existing timeline item (place is append-at-frame; lift is delete).
- Script GUIs (UIManager) on free, since 19.1.
- Out-of-process scripting on free.
- `LinkProxyMedia` is not exposed yet — importing a proxy folder edits those files as sources.

## Layout

```
src/video_harness/
  types.yaml                         marker type → color / scope
  harness.py                         inspect / import / place / mark
  session.py                         direct | HTTP | Lua
  scripts/video_harness_bridge.lua   in-app listener (free)
  scripts/vh_runtime.py              Python Resolve ops (Studio)
  mcp_server.py
```
