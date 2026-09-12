---
layout: default
title: License and attributions
nav_order: 8
---

# License and attributions

**video-harness** is copyright 2026 Saketha Ramanjam, released under the [MIT License](https://github.com/sakethramanujam/video-harness/blob/main/LICENSE).

This page lists the work we implement against, depend on, or learned from. None of the owners below endorse this project unless they say so themselves.

## This project

| | |
|---|---|
| License | [MIT](https://github.com/sakethramanujam/video-harness/blob/main/LICENSE) |
| Copyright | 2026 Saketha Ramanjam |
| Source | [github.com/sakethramanujam/video-harness](https://github.com/sakethramanujam/video-harness) |
| Docs | [sakethramanujam.github.io/video-harness](https://sakethramanujam.github.io/video-harness/) |

## Host application (not redistributed)

DaVinci Resolve, Fusion, fuscript, and the Resolve scripting API are products of **Blackmagic Design Pty Ltd**. This repo does not include Resolve. You must install it yourself.

We drive the published scripting surface (`scriptapp`, `MediaPool.ImportMedia`, `TimelineItem.SetClipColor`, markers, Fusion Scripts). Behavior of free vs Studio (external scripting, UIManager) is as Blackmagic documents it.

| | |
|---|---|
| Product | [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) |
| Support / downloads | [blackmagicdesign.com/support](https://www.blackmagicdesign.com/support/) |
| Scripting notes | Bundled with Resolve: `DaVinci Resolve.app/Contents/Resources/Developer/Scripting/` (README and examples). Not copied here. |
| Title / generator / property APIs | `Timeline.InsertFusionTitleIntoTimeline`, `InsertTitleIntoTimeline`, `InsertGeneratorIntoTimeline`, `TimelineItem.SetProperty` / `GetProperty` (Pan, Tilt, ZoomX/Y, Opacity, …). `TimelineItem.AddTransition` is documented from Resolve 21.1; 21.0.4.5 may return none. |
| Trademarks | DaVinci Resolve, Fusion, Blackmagic Design, and related marks belong to Blackmagic Design Pty Ltd. |

App Store “Lite” sandboxing (`com.blackmagic-design.DaVinciResolveLite`) is Apple’s and Blackmagic’s packaging, not ours.

## Protocol and Python stack

| Work | Role here | License (upstream) | Citation |
|---|---|---|---|
| [Model Context Protocol](https://modelcontextprotocol.io) | Tool/resource wire format for agents | See spec site | Anthropic PBC and MCP contributors, *Model Context Protocol* specification |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (`mcp`) | stdio MCP server (`FastMCP` / `MCPServer`) | MIT | [python-sdk LICENSE](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE) |
| [Pydantic](https://github.com/pydantic/pydantic) | Tool argument models | MIT | Copyright Samuel Colvin and contributors |
| [PyYAML](https://github.com/yaml/pyyaml) | `types.yaml` marker registry | MIT | Copyright Kirill Simonov and contributors; YAML 1.1 |
| [pytest](https://github.com/pytest-dev/pytest) | Tests (optional extra) | MIT | Holger Krekel and contributors |
| [setuptools](https://github.com/pypa/setuptools) | Package build | MIT | Python Packaging Authority |
| Python 3.10+ | Runtime | [PSF License](https://docs.python.org/3/license.html) | Python Software Foundation |
| Lua 5.1 / LuaJIT | Resolve Fusion scripts | MIT (Lua) / LuaJIT license | PUC-Rio; Mike Pall / LuaJIT.org. Fusion embeds Lua; we author `.lua` against that VM. |

JSON on the Lua file-queue follows [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) (IETF).

POSIX `fcntl` file locks (serial RPC) are IEEE Std 1003.1.

## Documentation site

| Work | Role here | License (upstream) | Citation |
|---|---|---|---|
| [Jekyll](https://jekyllrb.com) | Static site from `docs/` | MIT | Tom Preston-Werner, Parker Moore, and contributors |
| [just-the-docs](https://github.com/just-the-docs/just-the-docs) v0.10.1 | Docs theme (`remote_theme`) | MIT | [just-the-docs LICENSE](https://github.com/just-the-docs/just-the-docs/blob/main/LICENSE) |
| [github-pages](https://github.com/github/pages-gem) gem | Local/CI Jekyll stack | MIT | GitHub |
| [actions/checkout](https://github.com/actions/checkout), [configure-pages](https://github.com/actions/configure-pages), [jekyll-build-pages](https://github.com/actions/jekyll-build-pages), [upload-pages-artifact](https://github.com/actions/upload-pages-artifact), [deploy-pages](https://github.com/actions/deploy-pages) | GitHub Pages deploy | MIT (Actions) | GitHub, Inc. |

## Agents and hosts

| Work | Role here | Citation |
|---|---|---|
| [Grok](https://x.ai) / Grok Build TUI | MCP client used in development | xAI. Product names are xAI’s. |
| Antigravity CLI (`agy`) | Peer agent on vision/RFC work in this tree | Google Antigravity CLI. Not bundled. |

## Craft and persona

Agent operating rules in `AGENTS.md` follow:

> Balaji Srinivasan, *[The Samurai Engineer: 7 Japanese Philosophies for Technical Mastery](https://balaaagi.in/posts/the-samurai-engineer/)* (6 Sep 2025).

The seven named ideas are older than that essay. We cite Srinivasan as the engineering mapping we use, not as the origin of the Japanese terms:

| Term | Sense we use | Notes |
|---|---|---|
| Shugyō | Relentless practice | Traditional; see Srinivasan §Shugyō |
| Ikigai | Reason for the small API surface | Popularized in English in many places; we mean the intersection he describes |
| Kodawari | Invisible quality | |
| Shikata ga nai | Accept Lite/sandbox limits | |
| Kintsugi | Leave failures in docs and tests | Ceramic repair tradition, Japan |
| Kaizen | Small daily improvement | Toyota Production System / Imai, *Kaizen* (1986) is the usual English industrial citation |
| Danshari | Subtract extras (Scripts copies, session scratch) | Hideko Yamashita’s decluttering coinage, later popularized in English |

Srinivasan also points to a [Daily Sabah roundup of Japanese concepts](https://www.dailysabah.com/life/big-in-japan-10-japanese-concepts-to-live-by/).

## Algorithms and media conventions

| Work | Role here | Citation |
|---|---|---|
| Difference hash (dHash) | Optional vision pre-filter (skip static frames) | Neal Krawetz, *Looks Like It* (2011) and *Kind of Like That* (2013), The Hacker Factor Blog: [Looks Like It](https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html), [Kind of Like That](https://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html) |
| Hamming distance | Compare dHash bits | Richard Hamming, “Error Detecting and Error Correcting Codes,” *Bell System Technical Journal* 29(2), 1950 |
| Presentation timestamps / edit lists | Frame-accurate source in/out (vision RFC) | ISO/IEC 14496-12 (ISO BMFF / `elst`); Apple [Video Toolbox](https://developer.apple.com/documentation/videotoolbox) |
| Apple Metal / Mach task info | Memory caps in vision notes | Apple Inc. documentation; Metal allocations are not POSIX `RLIMIT_DATA` |
| DJI clip names `DJI_YYYYMMDDHHmmss_*` | Sort/cluster camera originals | Filename convention of DJI products. DJI is a trademark of SZ DJI Technology Co., Ltd. We parse names; we do not ship DJI software. |

Pillow (optional, BSD-style HPND) may accelerate dHash when installed; it is not a required dependency.

## Clip colors vs marker colors

Resolve’s `TimelineItem.SetClipColor` palette (Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate) and marker colors (Cyan, Mint, Red, …) come from **Blackmagic’s scripting API**, not from this repo. Aliases here (Cyan→Teal, Mint→Lime, Red→Violet) are ours, so agents do not pass marker names into `SetClipColor`.

## What we do not claim

- Ownership of DaVinci Resolve, Fusion, or any Blackmagic sample script
- Affiliation with Blackmagic Design, Apple, DJI, xAI, Google, or Anthropic
- Redistribution of MLX, Qwen, or other model weights (vision notes may *name* them; they are not in this tree’s required install)

If you add a dependency or copy an algorithm, add a row here in the same change.
