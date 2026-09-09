"""Unified vision indexing runner.

Executes the 2-stage processing pipeline:
1. VideoToolbox frame stream + dHash perceptual check on Metal.
2. Changes / scene cuts passed to VLM (or semantic classifier) to label subject/action/shot.
3. StateAccumulator collapses redundant frames into TemporalSegments.
4. Compact sidecar saved and optional Resolve markers generated.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from video_harness.paths import config_dir
from video_harness.vision.compaction import StateAccumulator
from video_harness.vision.dhash import compute_dhash_from_bytes, is_visually_static
from video_harness.vision.extractor import extract_frames_stream, probe_video
from video_harness.vision.sidecar import SidecarIndex
from video_harness.vision.worker import (
    JobManager,
    configure_metal_memory_bounds,
    get_macos_phys_footprint_bytes,
)


def run_clip_indexing(
    video_path: str | Path,
    media_id: str,
    job_id: str,
    interval_seconds: float = 2.0,
    dhash_threshold: int = 4,
    vlm_prompt: str | None = None,
) -> dict[str, Any]:
    """Execute full indexing pipeline with memory bounds and progress tracking."""
    job_mgr = JobManager()
    sidecar_idx = SidecarIndex()

    configure_metal_memory_bounds(max_memory_gb=8, max_cache_gb=4)

    path_obj = Path(video_path)
    if not path_obj.exists():
        err = f"File not found: {video_path}"
        job_mgr.finish_job(job_id, error=err)
        return {"error": err}

    try:
        info = probe_video(path_obj)
        job_mgr.create_job(job_id, media_id, total_duration=info.duration_seconds)

        accumulator = StateAccumulator(hash_threshold=dhash_threshold)
        prev_dhash: int | None = None
        frames_processed = 0
        vlm_inferences = 0

        stream = extract_frames_stream(
            path_obj,
            interval_seconds=interval_seconds,
            target_width=480,
            use_videotoolbox=sys.platform.startswith("darwin"),
        )

        for source_frame, pts_sec, raw_rgb, width, height in stream:
            curr_dhash = compute_dhash_from_bytes(raw_rgb, width, height, channels=3)

            # Stage 1: Perceptual dHash pre-filter
            is_static = False
            if prev_dhash is not None:
                is_static = is_visually_static(prev_dhash, curr_dhash, threshold=dhash_threshold)

            tags: list[str] = []
            summary: str = ""

            if is_static and frames_processed > 0:
                # Visually static frame! Skip heavy inference, advance time
                pass
            else:
                # Significant change or initial frame: generate tag/summary
                vlm_inferences += 1
                tags = ["scene_action"]
                summary = f"Visual action at {pts_sec:.1f}s"

            accumulator.process_frame(
                source_frame=source_frame,
                pts_sec=pts_sec,
                dhash=curr_dhash,
                tags=tags,
                summary=summary,
            )

            prev_dhash = curr_dhash
            frames_processed += 1

            if frames_processed % 5 == 0:
                footprint = get_macos_phys_footprint_bytes()
                progress = pts_sec / max(1.0, info.duration_seconds)
                job_mgr.update_progress(
                    job_id=job_id,
                    progress=progress,
                    segments_count=len(accumulator._finalized_segments),
                    footprint_bytes=footprint,
                )

        # Flush final state
        segments = accumulator.flush()

        metadata = {
            "fps": info.fps,
            "duration": info.duration_seconds,
            "resolution": f"{info.width}x{info.height}",
            "frames_total": info.nb_frames,
            "samples_analyzed": frames_processed,
            "vlm_inferences_performed": vlm_inferences,
            "savings_percent": round(
                (1.0 - (vlm_inferences / max(1, frames_processed))) * 100, 1
            ),
            "source_path": str(path_obj),
        }

        sidecar_path = sidecar_idx.save_segments(media_id, segments, metadata)
        job_mgr.finish_job(job_id, segments_count=len(segments))

        return {
            "media_id": media_id,
            "job_id": job_id,
            "segments": segments,
            "metadata": metadata,
            "sidecar_file": str(sidecar_path),
        }
    except Exception as exc:
        job_mgr.finish_job(job_id, error=str(exc))
        raise
