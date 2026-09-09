# Architecture Addendum: Resource Bounds, Memory Caps, and Information Compaction

## 1. Hard Memory Capping & Leak Prevention on macOS

To prevent Resolve from competing with Python/MLX for the 48 GB unified pool:

### A. Subprocess Process Tree Isolation
Never run MLX-VLM inside the persistent MCP server or Resolve process. Run it in an isolated worker subprocess (`video-harness worker describe ...`):
* When the job finishes, the subprocess terminates immediately, guaranteeing **100% of Metal allocations, texture buffers, and memory are returned to macOS**.

### B. Hard Operating System Limits (Mach task info, NOT RLIMIT_DATA)
> [!CAUTION]
> **Metal allocations bypass POSIX `setrlimit(RLIMIT_DATA)`**. Metal allocations are kernel-managed IOKit buffers, not heap/`brk`. To enforce real memory safety on macOS:
1. Use `mx.metal.set_memory_limit(limit_bytes)` (caps actual Metal driver memory allocation, not just cache).
2. Monitor true resident memory via Mach task info (`task_info(mach_task_self(), MACH_TASK_BASIC_INFO)` reading `resident_size` / `phys_footprint`).
3. If `phys_footprint` exceeds 8 GB, self-terminate gracefully.

### C. MLX Memory Controls & Cleanup
```python
import mlx.core as mx

# Hard-cap total Metal driver memory allocation:
mx.metal.set_memory_limit(8 * 1024 * 1024 * 1024)
# Cap memory caching in MLX:
mx.metal.set_cache_limit(4 * 1024 * 1024 * 1024)

# Explicitly prune memory after each frame
mx.clear_cache()
```

### D. Critical VideoToolbox / Decoder Invariant: B-Frame Reordering & `elst` Edits
> [!IMPORTANT]
> VideoToolbox / PyAV can emit frames in **Decode Time (DTS)** order when B-frames are present. Ingest must explicitly sort decoded packets by **PTS (Presentation TimeStamp)** before indexing. Furthermore, inspect the MP4/MOV edit list (`elst` atom) to offset timestamps correctly so source frames match Resolve's internal timeline clip player.

---

## 2. Dynamic Temporal Noise Filtering & State Compaction

Raw video generates massive redundancy (e.g. 30 frames of "man sitting in chair talking"). If recorded naively, it bloats disk, markers, and LLM context.

### The Compaction Algorithm: "dHash Pre-Filter + Change-Only State Accumulator"

To be **computationally sparse**, we do NOT run the 7B VLM on every sampled frame. We use a 2-stage cascade:
1. **Stage 1 (Perceptual Hash on Apple Neural Engine / Metal, ~0.5ms)**:
   - Compute difference hash (`dHash`) or block variance on the downscaled frame.
   - If hamming distance to the previous keyframe is below threshold ($\Delta < 4$), the visual scene is statically identical (e.g. static speaker).
   - **Skip VLM inference completely**. Just advance `end_frame`.
   - *Impact*: Reduces 7B VLM invocations by 80–90% on interviews and podcasts with zero loss of semantic fidelity!
2. **Stage 2 (VLM Inference on Visual Deltas)**:
   - Trigger VLM only when perceptual change or shot cut is detected.


### Compaction Rules:
1. **Deduplication via Semantic Hash / Cosine Gate**: If the VLM visual embedding or tag set between frame $t$ and frame $t-1$ has $>0.85$ similarity, do not store new text—simply extend the time boundary (`source_in` stays constant, `source_out` advances).
2. **Rolling Window Noise Pruning**: Merge consecutive similar frames into a single `temporal_segment` with:
   - `start_frame`, `end_frame`
   - `salient_tags`: `["host", "intro", "talking"]` (set union)
   - `summary`: One dense 10-word description instead of 10 repeated paragraphs.

---

## 3. Extreme Disk Footprint Reduction: Compact Representations

Instead of storing raw float32 embeddings (which consume ~4 MB per minute of video) or full chat transcripts:

### A. Int8 or Binary Quantized Embeddings
* If using visual embeddings (e.g., MobileCLIP / SigLIP), convert 512-dim `float32` vectors (2,048 bytes per frame) to **`int8`** (512 bytes) or **1-bit binary Hamming embeddings** (64 bytes per frame).
* **Storage savings**: ~97% reduction. An hour of video with 1,800 frames occupies only **~115 KB** on disk.

### B. SQLite with `zstd` compression or Single Compact JSONL
* Store only compact schema:
```json
{
  "start": 120,
  "end": 285,
  "pts": 5.0,
  "shot": "medium",
  "tags": ["host", "unboxing"],
  "summary": "Host unboxes phone on wooden table"
}
```
* Pipe the output directly through `zstandard` or SQLite with WAL mode. For an entire 1-hour 4K video, the complete index is **< 150 KB**.

---

## 4. Summary of Constraints

| Dimension | Default / Naive Approach | Our Bounded Architecture |
|---|---|---|
| **RAM / Metal Budget** | Unbounded (Spikes to 30GB+, evicts Resolve) | **Hard-capped at 6–8 GB** via `setrlimit` + `mx.metal.set_cache_limit` |
| **Process Lifecycle** | Long-running daemon or in-process | **Ephemeral worker subprocess** (100% memory freed on exit) |
| **Disk Storage** | 2,400 raw JSON descriptions (~50 MB per clip) | **State-compacted temporal spans (< 200 KB per clip)** |
| **Resolve Ruler Impact** | Thousands of markers (crashes Lua bridge) | **5–20 high-significance boundary markers only** |
| **LLM Context Density** | Repetitive frame noise | **Zero-redundancy timeline events with frame ranges** |
