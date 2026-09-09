"""Automated style-driven rough cut editing assistant for DaVinci Resolve Free edition.

Enhanced capabilities:
- Library-wide multi-clip assembly across the entire imported media pool.
- Telemetry & metadata awareness (GPS altitude, flight pattern, duration, timestamps).
- Dynamic, meaningful clip durations (cinematic 4-8s, dynamic 3-5s, social 2-3s).
- Title & chapter marker generation on the edit ruler with location/telemetry data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from video_harness.harness import Harness
from video_harness.vision.sidecar import SidecarIndex
from video_harness.vision.telemetry import find_companion_srt, parse_telemetry_srt


STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "cinematic_narrative": {
        "description": "Epic, immersive pacing: 4-8s cuts with gradual altitude/scenery reveals.",
        "min_clip_duration_sec": 4.0,
        "target_clip_duration_sec": 6.0,
        "max_clip_duration_sec": 8.0,
        "clip_color": "Teal",
    },
    "montage": {
        "description": "Dynamic rhythm cut: alternates action and scenery at 3-4s per clip.",
        "min_clip_duration_sec": 2.5,
        "target_clip_duration_sec": 3.5,
        "max_clip_duration_sec": 5.0,
        "clip_color": "Blue",
    },
    "fast_paced_social": {
        "description": "Short snappy hooks (1.5-2.5s) designed for high retention reels/shorts.",
        "min_clip_duration_sec": 1.5,
        "target_clip_duration_sec": 2.0,
        "max_clip_duration_sec": 3.0,
        "clip_color": "Orange",
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
        user_prompt: str | None = None,
        add_title_markers: bool = True,
    ) -> dict[str, Any]:
        """Assemble a cohesive rough cut across the entire imported library.

        1. Inspects all clips in current media pool.
        2. Enriches each clip with telemetry (GPS altitude, flight pattern from .SRT).
        3. Sorts and filters clips by chronological order or flight movement variety.
        4. Calculates meaningful durations (e.g. 4-8s for cinematic, not tiny 1s loops).
        5. Places all clips on Track V1.
        6. Adds chapter/title markers on the timeline with telemetry & location context.
        """
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["cinematic_narrative"])
        snap = self.harness.inspect(media="current")
        all_clips = snap.get("media", {}).get("clips", [])
        video_clips = [c for c in all_clips if c.get("path", "").lower().endswith((".mp4", ".mov"))]

        if not video_clips:
            return {"error": "No video clips found in media pool to assemble.", "placed": []}

        # Enrich clips with companion telemetry metadata
        enriched_clips: list[dict[str, Any]] = []
        for c in video_clips:
            path_str = c.get("path")
            telemetry: dict[str, Any] = {}
            if path_str:
                srt_path = find_companion_srt(path_str)
                if srt_path:
                    telemetry = parse_telemetry_srt(srt_path)

            enriched = dict(c)
            enriched["telemetry"] = telemetry
            enriched_clips.append(enriched)

        # Sort chronologically by telemetry start time or clip name
        enriched_clips.sort(key=lambda x: (x.get("telemetry", {}).get("start_time") or x.get("name") or ""))

        # Filter by prompt query if provided, else take sample across the library
        if user_prompt:
            p_lower = user_prompt.lower()
            filtered = [
                c for c in enriched_clips
                if p_lower in c.get("name", "").lower() or p_lower in c.get("telemetry", {}).get("movement_profile", "")
            ]
            selected = filtered if filtered else enriched_clips
        else:
            selected = enriched_clips

        # Limit to max_clips while preserving narrative span across the library
        if len(selected) > max_clips:
            step = len(selected) / float(max_clips)
            selected = [selected[int(i * step)] for i in range(max_clips)]

        self.harness.ensure_timeline(timeline_name)

        items_to_place: list[dict[str, Any]] = []
        title_markers: list[dict[str, Any]] = []
        accumulated_record_frame = 86400  # Default 01:00:00:00 start frame in Resolve

        for idx, clip in enumerate(selected):
            fps = float(clip.get("fps") or 29.97)
            total_frames = int(clip.get("frames") or 300)

            target_duration_sec = preset["target_clip_duration_sec"]
            target_duration_frames = int(target_duration_sec * fps)

            # Avoid gimbal startup and landing jitter by taking a stabilized section from the middle
            if total_frames > (target_duration_frames + 120):
                start_f = 120
            elif total_frames > target_duration_frames:
                start_f = (total_frames - target_duration_frames) // 2
            else:
                start_f = 0
                target_duration_frames = max(24, total_frames)

            end_f = min(start_f + target_duration_frames, total_frames)
            actual_duration = end_f - start_f

            items_to_place.append({
                "media_id": clip["media_id"],
                "source_in": start_f,
                "source_out": end_f,
                "track_type": "video",
                "track_index": 1,
            })

            # Create title/telemetry marker
            tel = clip.get("telemetry", {})
            alt_info = f"{tel.get('avg_alt_m', 0.0)}m" if tel.get("avg_alt_m") else ""
            profile = tel.get("movement_profile", "shot")
            title_text = f"Scene {idx + 1}: {clip['name']}"
            if alt_info:
                title_text += f" | Alt: {alt_info} ({profile})"

            title_markers.append({
                "type": "chapter",
                "frame": accumulated_record_frame,
                "name": f"Scene-{idx + 1}",
                "note": title_text,
                "color": "Purple",
            })

            accumulated_record_frame += actual_duration

        # Place the clips
        placed_res = self.harness.place(items_to_place)

        # Set clip colors on the newly placed items
        placed_uids = [
            item["unique_id"]
            for item in placed_res.get("placed", [])
            if item.get("unique_id")
        ]
        if placed_uids:
            try:
                self.harness.set_clip_color(color=preset["clip_color"], unique_ids=placed_uids)
            except Exception:
                pass

        # Add section title/chapter markers
        if add_title_markers and title_markers:
            self.harness.marker_upsert(title_markers)


        return {
            "timeline": timeline_name,
            "style": style,
            "cuts_count": len(items_to_place),
            "clips_placed_count": len(items_to_place),
            "library_total_analyzed": len(video_clips),
            "placed_items": items_to_place,

            "title_markers": title_markers,
            "result": placed_res,
            "feedback_suggestions": [
                f"Generated a {style} cut using {len(items_to_place)} unique clips with meaningful durations (avg {preset['target_clip_duration_sec']}s).",
                "Added Chapter markers on each scene boundary with altitude and flight telemetry.",
                "Would you like to extend or trim specific scene ranges, or re-order based on flight altitude (high reveals -> low flyovers)?",
            ],
        }

    def generate_draft_cut(
        self,
        timeline_name: str,
        media_id: str,
        style: str = "montage",
        user_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Legacy helper for single-clip draft cuts."""
        return self.assemble_library_cut(
            timeline_name=timeline_name,
            style=style,
            max_clips=10,
            user_prompt=user_prompt,
        )
