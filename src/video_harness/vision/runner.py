"""Unified vision indexing runner.

Executes the spatio-temporal scene indexing pipeline:
1. VideoToolbox hardware-accelerated frame stream + perceptual dHash check.
2. SpatioTemporalSceneAnalyzer analyzes frame spatial composition:
   - Dynamic luminance & contrast distribution.
   - High-frequency edge gradient energy (detecting focus, landscape, detail vs blank ground/sky).
   - Temporal optical difference & motion stability (distinguishes smooth pans vs erratic jitter vs static).
3. Quality gating:
   - Classifies shot types (wide_establishing, medium_scenic, close_detail, or uncomposed_dead_frame).
   - Flags unusable frames (muddy/low-contrast, severe camera jitter, dead setups).
4. StateAccumulator collapses redundant frames into compact TemporalSegments.
5. Generates rich sidecar metadata and Resolve-ready markers.
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
from video_harness.vision.spatio_temporal import SpatioTemporalSceneAnalyzer
from video_harness.vision.telemetry import find_companion_srt, parse_telemetry_srt
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
    quality_threshold: float = 4.5,
    vlm_prompt: str | None = None,
) -> dict[str, Any]:
    """Execute full spatio-temporal indexing pipeline with memory bounds and progress tracking."""
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

        # Look for companion telemetry metadata if available (drone, GoPro, or EXIF)
        srt_path = find_companion_srt(path_obj)
        telemetry = parse_telemetry_srt(srt_path) if srt_path else {}

        analyzer = SpatioTemporalSceneAnalyzer(quality_threshold=quality_threshold)
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

        curr_seg_start_f = 0
        curr_seg_start_pts = 0.0

        for source_frame, pts_sec, raw_rgb, width, height in stream:
            curr_dhash = compute_dhash_from_bytes(raw_rgb, width, height, channels=3)

            # Spatio-temporal analysis on actual frame pixels
            metrics, motion = analyzer.process_frame(
                raw_rgb=raw_rgb,
                width=width,
                height=height,
                pts_sec=pts_sec,
                source_frame=source_frame,
            )

            is_static = False
            if prev_dhash is not None:
                is_static = is_visually_static(prev_dhash, curr_dhash, threshold=dhash_threshold)

            # Determine tags & semantic summary for this sample point
            tags: list[str] = []
            summary: str = ""

            if is_static and frames_processed > 0:
                # Visually static frame! Retain state, skip redundant re-indexing
                tags = ["static_hold"]
                summary = f"Static hold at {pts_sec:.1f}s"
            else:
                vlm_inferences += 1
                # Synthesize scene info using vision metrics & metadata
                scene = analyzer.synthesize_scene(
                    start_frame=curr_seg_start_f,
                    end_frame=source_frame,
                    start_pts=curr_seg_start_pts,
                    end_pts=pts_sec,
                    camera_metadata=telemetry,
                )
                tags = scene.tags
                summary = scene.summary
                curr_seg_start_f = source_frame
                curr_seg_start_pts = pts_sec

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
            "telemetry": telemetry,
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
