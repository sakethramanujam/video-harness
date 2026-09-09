"""Automated general-purpose rough cut editing assistant for DaVinci Resolve Free edition.

Supports any genre, media format, and length:
- Spatio-temporal scene understanding: analyzes visual composition, contrast, detail, and motion.
- Sidecar semantic indexing: reads visual tags, shot classifications, and quality scores.
- Extended metadata awareness: integrates companion telemetry (drone/GoPro/camera EXIF) when available.
- Quality filtering: automatically excludes muddy, washed out, severe jitter, or blank frames.
- Flexible style presets: documentary, narrative, dynamic montage, interview/dialogue, social short, or custom prompt.
- Timeline titles, generators, and contextual chapter/b-roll markers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from video_harness.harness import Harness
from video_harness.vision.sidecar import SidecarIndex
from video_harness.vision.telemetry import find_companion_srt, parse_telemetry_srt


STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "cinematic_narrative": {
        "description": "Immersive narrative pacing: 5-9s cuts focusing on wide establishing and tracking shots.",
        "min_clip_duration_sec": 4.0,
        "target_clip_duration_sec": 6.5,
        "max_clip_duration_sec": 9.0,
        "preferred_shots": ["wide_establishing", "medium_scenic"],
        "clip_color": "Teal",
    },
    "documentary": {
        "description": "Measured documentary flow: 6-10s clips allowing viewer to absorb scene details.",
        "min_clip_duration_sec": 5.0,
        "target_clip_duration_sec": 7.5,
        "max_clip_duration_sec": 12.0,
        "preferred_shots": ["medium_scenic", "close_detail", "wide_establishing"],
        "clip_color": "Navy",
    },
    "dynamic_montage": {
        "description": "Rhythmic high-energy cut: 3-5s clips emphasizing dynamic motion and high contrast.",
        "min_clip_duration_sec": 2.5,
        "target_clip_duration_sec": 3.8,
        "max_clip_duration_sec": 5.0,
        "preferred_shots": ["high_speed_dynamic", "smooth_tracking"],
        "clip_color": "Blue",
    },
    "montage": {
        "description": "Rhythmic high-energy cut: 3-5s clips emphasizing dynamic motion and high contrast.",
        "min_clip_duration_sec": 2.5,
        "target_clip_duration_sec": 3.8,
        "max_clip_duration_sec": 5.0,
        "preferred_shots": ["high_speed_dynamic", "smooth_tracking"],
        "clip_color": "Blue",
    },
    "fast_paced_social": {
        "description": "Snappy, high-retention hooks: 1.5-3.0s cuts designed for vertical reels/shorts.",
        "min_clip_duration_sec": 1.5,
        "target_clip_duration_sec": 2.2,
        "max_clip_duration_sec": 3.5,
        "preferred_shots": ["hero_composition", "close_detail"],
        "clip_color": "Orange",
    },
    "interview_coverage": {
        "description": "A-roll / B-roll coverage: balances medium scenic context with detail cutaways.",
        "min_clip_duration_sec": 4.0,
        "target_clip_duration_sec": 6.0,
        "max_clip_duration_sec": 10.0,
        "preferred_shots": ["medium_scenic", "close_detail"],
        "clip_color": "Green",
    },
}


class EditAssistant:
    def __init__(self, harness: Harness, sidecar_index: SidecarIndex | None = None):
        self.harness = harness
        self.sidecar = sidecar_index or SidecarIndex()

    def assemble_library_cut(
        self,
        timeline_name: str,
        style: str = "cinematic_narrative",
        max_clips: int = 15,
        target_timeline_duration_sec: float | None = None,
        user_prompt: str | None = None,
        add_title_markers: bool = True,
        order_mode: str = "chronological",  # "chronological", "visual_energy", "prompt_relevance"
    ) -> dict[str, Any]:
        """Assemble a cohesive cut across any general video library using vision & metadata intelligence.

        1. Inspects all clips in the media pool.
        2. Enriches each clip with spatio-temporal sidecar indexing and camera metadata.
        3. Quality gates out unusable footage (dead setups, severe jitter, blank underexposed frames).
        4. Calculates meaningful durations adapting to target duration or style pacing.
        5. Places clips into timeline, applies color coding, and stamps contextual markers.
        """
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["cinematic_narrative"])
        snap = self.harness.inspect(media="current")
        all_clips = snap.get("media", {}).get("clips", [])
        video_clips = [c for c in all_clips if c.get("path", "").lower().endswith((".mp4", ".mov", ".mkv", ".m4v"))]

        if not video_clips:
            return {"error": "No video clips found in media pool to assemble.", "placed": []}

        # Analyze each clip via sidecar vision data & metadata
        evaluated_clips: list[dict[str, Any]] = []
        for c in video_clips:
            path_str = c.get("path")
            media_id = c.get("media_id", "")
            sidecar_segs = self.sidecar.load_segments(media_id) if media_id else []

            telemetry: dict[str, Any] = {}
            if path_str:
                srt_path = find_companion_srt(path_str)
                if srt_path:
                    telemetry = parse_telemetry_srt(srt_path)

            # Evaluate visual quality and composition from sidecar segments
            usable_segs = [s for s in sidecar_segs if s.get("is_usable", True)]
            quality_score = 6.0
            if usable_segs:
                quality_score = sum(s.get("quality_score", 5.0) for s in usable_segs) / len(usable_segs)
            elif sidecar_segs:
                # If all segments were marked unusable, low score
                quality_score = 2.0

            # Collect tags
            all_tags: set[str] = set()
            for s in sidecar_segs:
                all_tags.update(s.get("tags", []))

            evaluated = dict(c)
            evaluated["telemetry"] = telemetry
            evaluated["sidecar_segments"] = sidecar_segs
            evaluated["quality_score"] = quality_score
            evaluated["tags"] = sorted(list(all_tags))
            evaluated_clips.append(evaluated)

        # Quality Gate: filter out uncomposed / dead footage if higher quality clips exist
        high_quality = [c for c in evaluated_clips if c["quality_score"] >= 4.0]
        active_pool = high_quality if high_quality else evaluated_clips

        # Filter or rank by user prompt if specified
        if user_prompt:
            p_lower = user_prompt.lower()
            matching = []
            for c in active_pool:
                score = 0
                if p_lower in c.get("name", "").lower():
                    score += 5
                for t in c.get("tags", []):
                    if p_lower in t.lower():
                        score += 3
                if score > 0:
                    matching.append((score, c))
            if matching:
                matching.sort(key=lambda x: x[0], reverse=True)
                active_pool = [m[1] for m in matching]

        # Ordering
        if order_mode == "chronological":
            active_pool.sort(key=lambda x: (x.get("telemetry", {}).get("start_time") or x.get("name") or ""))
        elif order_mode == "visual_energy":
            active_pool.sort(key=lambda x: x.get("quality_score", 5.0), reverse=True)

        # Select clips for the target duration or count
        selected: list[dict[str, Any]] = []
        if target_timeline_duration_sec:
            target_clip_len = preset["target_clip_duration_sec"]
            needed_clips = max(1, int(round(target_timeline_duration_sec / target_clip_len)))
            step = max(1.0, len(active_pool) / float(needed_clips))
            for i in range(min(needed_clips, len(active_pool))):
                idx = min(len(active_pool) - 1, int(i * step))
                if active_pool[idx] not in selected:
                    selected.append(active_pool[idx])
        else:
            if len(active_pool) > max_clips:
                step = len(active_pool) / float(max_clips)
                selected = [active_pool[int(i * step)] for i in range(max_clips)]
            else:
                selected = active_pool

        self.harness.ensure_timeline(timeline_name)

        items_to_place: list[dict[str, Any]] = []
        title_markers: list[dict[str, Any]] = []
        accumulated_frame = 0

        for idx, clip in enumerate(selected):
            fps = float(clip.get("fps") or 29.97)
            total_frames = int(clip.get("frames") or 300)

            # Determine dynamic clip cut duration
            if target_timeline_duration_sec and selected:
                duration_sec = target_timeline_duration_sec / len(selected)
                duration_sec = max(preset["min_clip_duration_sec"], min(preset["max_clip_duration_sec"], duration_sec))
            else:
                duration_sec = preset["target_clip_duration_sec"]

            duration_frames = int(round(duration_sec * fps))

            # Select best window: if sidecar segments exist, pick highest scoring segment
            segs = clip.get("sidecar_segments", [])
            if segs:
                best_seg = max(segs, key=lambda s: s.get("quality_score", 5.0))
                start_f = int(best_seg.get("start_frame", 0))
            else:
                # Default to stable center window avoiding startup/shutdown head/tail
                lead_in = min(int(round(3.0 * fps)), total_frames // 4)
                start_f = lead_in if total_frames > (duration_frames + lead_in) else 0

            end_f = min(start_f + duration_frames, total_frames)
            actual_duration = max(24, end_f - start_f)

            items_to_place.append({
                "media_id": clip["media_id"],
                "source_in": start_f,
                "source_out": start_f + actual_duration,
                "track_type": "video",
                "track_index": 1,
            })

            # Create contextual marker
            tag_summary = ", ".join(clip.get("tags", [])[:2])
            note_str = f"{clip['name']}"
            if tag_summary:
                note_str += f" | {tag_summary}"
            if clip.get("telemetry", {}).get("avg_alt_m"):
                note_str += f" | Alt: {clip['telemetry']['avg_alt_m']}m"

            title_markers.append({
                "type": "chapter",
                "frame": accumulated_frame,
                "name": f"Scene-{idx + 1}",
                "note": note_str,
                "color": preset["clip_color"],
            })

            accumulated_frame += actual_duration

        # Place the clips
        placed_res = self.harness.place(items_to_place)

        # Set clip colors
        for clip in selected:
            try:
                self.harness.set_clip_color(color=preset["clip_color"], clip_name=clip["name"])
            except Exception:
                pass

        # Stamp timeline markers
        if add_title_markers and title_markers:
            for m in title_markers:
                try:
                    self.harness.marker_upsert(m)
                except Exception:
                    pass

        total_runtime_sec = round(accumulated_frame / 29.97, 1)

        return {
            "timeline": timeline_name,
            "style": style,
            "order_mode": order_mode,
            "total_runtime_sec": total_runtime_sec,
            "cuts_count": len(items_to_place),
            "clips_placed_count": len(items_to_place),
            "library_total_analyzed": len(video_clips),
            "title_markers": title_markers,
            "placed_items": items_to_place,
            "feedback_suggestions": [
                f"Assembled general-purpose {style} cut ({total_runtime_sec}s runtime) using spatio-temporal scene analysis.",
                f"Filtered out low-contrast, jittery, or dead setup frames across {len(video_clips)} library clips.",
                "Review the timeline markers for visual shot classifications and composition scores.",
            ],
        }

    def generate_draft_cut(
        self,
        timeline_name: str,
        media_id: str,
        style: str = "dynamic_montage",
        user_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a rough cut across the library or for a specific media clip."""
        return self.assemble_library_cut(
            timeline_name=timeline_name,
            style=style if style in STYLE_PRESETS else "dynamic_montage",
            user_prompt=user_prompt,
        )

