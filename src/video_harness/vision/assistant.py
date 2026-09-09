"""Automated style-driven rough cut editing assistant for DaVinci Resolve Free edition.

Workflow:
1. Scan media folder, import clips into Resolve bin.
2. Index visual context using VideoToolbox + dHash pre-filter + sidecar storage.
3. Apply style templates (e.g. 'montage', 'talking_head_highlights', 'fast_paced_social', 'cinematic_broll').
4. Place rough-cut clips onto a fresh timeline.
5. Stamp chapter / scene.cut / visual.shot markers.
6. Provide structured feedback prompts for iterative revisions.
"""

from __future__ import annotations

from typing import Any
from video_harness.harness import Harness
from video_harness.vision.sidecar import SidecarIndex


STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "montage": {
        "description": "Dynamic rhythm cut: alternates action and scenery at 2-3s per clip.",
        "max_clip_duration_sec": 3.0,
        "clip_color": "Blue",
        "preferred_shots": ["action", "scenery", "broll"],
    },
    "talking_head_highlights": {
        "description": "Pulls key speaking moments and transitions into clean timeline assembly.",
        "max_clip_duration_sec": 8.0,
        "clip_color": "Green",
        "preferred_shots": ["host", "talking", "presentation"],
    },
    "fast_paced_social": {
        "description": "Short snappy hooks (1-2s) designed for high retention reels / shorts.",
        "max_clip_duration_sec": 2.0,
        "clip_color": "Orange",
        "preferred_shots": ["action", "product", "highlight"],
    },
}


class EditAssistant:
    def __init__(self, harness: Harness, sidecar_index: SidecarIndex | None = None):
        self.harness = harness
        self.sidecar = sidecar_index or SidecarIndex()

    def generate_draft_cut(
        self,
        timeline_name: str,
        media_id: str,
        style: str = "montage",
        user_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate a first pass video edit cut according to style or user prompt."""
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["montage"])
        segments = self.sidecar.load_segments(media_id)
        metadata = self.sidecar.load_metadata(media_id)
        fps = float(metadata.get("fps") or 24.0)

        if not segments:
            # Fallback: assemble raw clip if not indexed
            ensured = self.harness.ensure_timeline(timeline_name)
            placed = self.harness.place([{"media_id": media_id, "track_type": "video", "track_index": 1}])
            return {
                "timeline": timeline_name,
                "style": style,
                "status": "raw_assembly_fallback",
                "placed": placed,
                "note": "Media was not yet indexed in sidecar; placed raw clip.",
            }

        max_frames = int(preset["max_clip_duration_sec"] * fps)
        items_to_place: list[dict[str, Any]] = []

        # If user provided a specific prompt query, search for matching segments first
        if user_prompt:
            matches = self.sidecar.search(media_id, user_prompt, top_k=5)
            selected_segments = matches if matches else segments
        else:
            selected_segments = segments

        for seg in selected_segments:
            start_f = seg["start_frame"]
            end_f = seg["end_frame"]
            # Enforce max duration for style
            if (end_f - start_f) > max_frames:
                end_f = start_f + max_frames

            items_to_place.append({
                "media_id": media_id,
                "source_in": start_f,
                "source_out": end_f,
                "track_type": "video",
                "track_index": 1,
            })

        self.harness.ensure_timeline(timeline_name)
        placed_res = self.harness.place(items_to_place)

        # Apply style clip color
        self.harness.set_clip_color(color=preset["clip_color"], media_id=media_id)

        return {
            "timeline": timeline_name,
            "style": style,
            "style_description": preset["description"],
            "cuts_count": len(items_to_place),
            "placed_items": items_to_place,
            "result": placed_res,
            "feedback_suggestions": [
                "Are the cuts too fast or too slow for your intended pacing?",
                "Would you like to re-order the clips or inject B-roll over the dialogue?",
                "Should we color-code specific key moments (e.g. Lime for best takes)?",
            ],
        }
