# RFC 001 (Final): Edit-Aware Video Context via Local Metal (MLX-VLM) & Sidecar Index

**Status**: Approved (Synthesized with Grok Peer Review)  
**Target Hardware**: Apple Silicon (M5 Max, 48 GB Unified Memory)  
**Host App**: DaVinci Resolve (Free/Lite via Lua Bridge or Studio via Python API)  
**Authors**: Antigravity (`agy`) & Grok (`grok`)

---

## 1. Core Synthesis & Critical Architectural Corrections

Following the peer review between **Antigravity** and **Grok**, we identified 3 major failure modes in the initial design and synthesized these foundational fixes:

### 1. The Clock / Frame Rate Rule
* **Problem**: Sampling in wall-clock seconds (`timecode.py`) causes cumulative frame drift on 23.976 / 29.97 DF footage, resulting in cuts that miss the visual action.
* **Resolution**:
  - The single source of truth is **PTS (Presentation TimeStamp) / Source Frame Index** via VideoToolbox/PyAV.
  - Record `(pts_seconds, source_frame, media_fps)` per sample.
  - Compute `source_in` and `source_out` using **Clip FPS**, reserving Timeline FPS solely for display markers.

### 2. Metal Memory & Unified Budget Protection (Resolve + MLX)
* **Problem**: An open 4K Resolve timeline plus 2,400 raw image tokens concurrently in `mlx-vlm` will exhaust unified memory and trigger OS paging/crashes.
* **Resolution**:
  - Downscale extracted keyframes strictly to **448–672 px** max dimension.
  - Streaming pipeline: Decode → Infer 1 frame → `mx.clear_cache()` → Stream to JSONL.
  - Dedicated background process: VLM inference runs decoupled from the MCP server process; model weights are unloaded immediately when indexing finishes.
  - **Scene-Adaptive Sampling**: Combine shot cut detection (`scenedetect` or VideoToolbox PTS gaps) + 1 mid-shot frame, rather than a brute-force 1-second grid.

### 3. The Two-Tier Storage Hierarchy (Sidecar DB vs. Sparse Resolve Markers)
* **Problem**: Resolve's Lua file-bridge executes in-app polling (200 ms) with a 120s RPC timeout. Ingesting 2,000+ markers causes $O(N^2)$ table scans and marker collisions (only 1 marker permitted per frame).
* **Resolution**:
  - **Tier 1 (Dense Sidecar Index)**: Store frame-by-frame VLM tags and embeddings in `~/.config/video-harness/describe/<media_id>.jsonl`.
  - **Tier 2 (Sparse Resolve Markers)**: Stamp only significant scene transitions and query results (`scene.cut`, `chapter`, `visual.shot`) onto Resolve rulers using chunked `marker_upsert` (50–100 per call).
  - Search runs locally in Python against the JSONL sidecar (sub-millisecond), completely bypassing Lua bridge latency.

---

## 2. Updated Marker Types (`types.yaml`)

Add clean, space-free identifiers:
```yaml
types:
  scene.cut:
    color: Sky
    scope: clip
    duration: point
    description: Detected shot boundary / camera cut
  visual.shot:
    color: Mint
    scope: clip
    duration: range
    description: Semantic scene description or visual action range
  chapter:
    color: Purple
    scope: timeline
    duration: point
```

---

## 3. Final MCP Tool Interface

### 1. `clip_describe_start(media_id: str, sample_mode: "scene" | "dense") -> {"job_id": str}`
* Launches async background indexing process with memory ceiling.
* Uses Apple VideoToolbox hardware decode + `mlx-vlm` (Qwen2-VL-7B-4bit).
* Writes streaming records to `<media_id>.jsonl`.

### 2. `clip_describe_status(job_id: str) -> {"status": "running"|"done", "progress": float, "shots_found": int}`
* Allows agent to poll or await completion without blocking Lua RPC or hitting timeouts.

### 3. `clip_search_visual(media_id: str, query: str, top_k: int = 5) -> list[dict]`
* Instant search over local sidecar JSONL.
* Returns exact `source_in`, `source_out`, and confidence scores.

### 4. `timeline_cut_from_visual(media_id: str, timeline_name: str, queries: list[str])`
* Evaluates queries against sidecar index.
* Ensures/creates `timeline_name`.
* Invokes `timeline_place` with precise `source_frame` boundaries on the destination track.

---

## 4. Implementation Phasing

1. **Phase 1 (Precision Time & Sidecar Engine)**:
   - Implement `video_harness.vision.decoder` using PyAV/VideoToolbox.
   - Enforce exact PTS-to-source-frame calculation.
2. **Phase 2 (MLX-VLM Worker)**:
   - Build worker script running `Qwen2-VL-7B-4bit` with resolution cap (512px) and batch size 1.
3. **Phase 3 (MCP Endpoints & Types)**:
   - Register `scene.cut` and `visual.shot` in `types.yaml`.
   - Implement `clip_describe_*`, `clip_search_visual`, and `timeline_cut_from_visual`.
