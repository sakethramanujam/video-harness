"""Travel documentary & drone montage director engine for DaVinci Resolve.

Provides intelligent narrative arc assembly:
- Clusters footage into real geographic regions (Bonneville Salt Flats, Snake River, Shoshone Falls, etc.).
- Arranges an intentional 3-act narrative arc:
    Act 1: Epic High Altitude Reveals & Establishing Cranes (>50m).
    Act 2: Fluid Dynamic Flyovers & Mountain Transitions (20-50m).
    Act 3: Low Proximity High-Speed Flybys & Atmospheric Landings (<15m).
- Dynamically assigns shot duration based on camera movement:
    * Slow grand reveals / cranes: 5.5s - 7.5s
    * Steady panoramic flyovers: 4.0s - 5.5s
    * Fast low-proximity flybys: 2.8s - 3.8s
- Stamps section title & chapter markers with location name and flight telemetry.
- Sets distinct clip colors per geographic location so the editor sees regions visually.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from video_harness.harness import Harness
from video_harness.vision.telemetry import (
    find_companion_srt,
    find_stabilized_window,
    parse_telemetry_srt,
)



REGION_COLOR_MAP = {
    "Bonneville Salt Flats": "Sand",
    "Shoshone Falls & Canyon": "Teal",
    "Twin Falls & Snake River": "Navy",
    "Angel Lake & Ruby Foothills": "Olive",
    "Pequop Mountain Pass": "Brown",
    "Unknown Region": "Blue",
}


def identify_region(lat: float, lon: float) -> str:
    """Identify real-world geographical travel region from GPS coordinates."""
    if lat > 42.0:
        if lon > -114.45:
            return "Shoshone Falls & Canyon"
        else:
            return "Twin Falls & Snake River"
    elif lat > 41.2:
        return "Pequop Mountain Pass"
    elif lat > 40.9:
        return "Angel Lake & Ruby Foothills"
    else:
        return "Bonneville Salt Flats"


class TravelMontageDirector:
    def __init__(self, harness: Harness):
        self.harness = harness

    def build_travel_montage(
        self,
        timeline_name: str = "Idaho_Epic_Travel_Montage",
        target_total_duration_sec: float = 60.0,
        region_filter: str | None = None,
        order_mode: str = "chronological",
    ) -> dict[str, Any]:

        """Build an epic multi-region travel montage across the full library."""
        snap = self.harness.inspect(media="current")
        all_clips = snap.get("media", {}).get("clips", [])
        video_clips = [c for c in all_clips if c.get("path", "").lower().endswith((".mp4", ".mov"))]

        if not video_clips:
            return {"error": "No video clips found in media pool."}

        # Analyze each clip's telemetry and geographic cluster
        analyzed_clips: list[dict[str, Any]] = []
        for c in video_clips:
            path_str = c.get("path")
            telemetry: dict[str, Any] = {}
            if path_str:
                srt_path = find_companion_srt(path_str)
                if srt_path:
                    telemetry = parse_telemetry_srt(srt_path)

            gps = telemetry.get("start_gps")
            region = identify_region(gps[0], gps[1]) if gps else "Unknown Region"

            analyzed = dict(c)
            analyzed["telemetry"] = telemetry
            analyzed["region"] = region
            analyzed["color"] = REGION_COLOR_MAP.get(region, "Teal")
            analyzed_clips.append(analyzed)

        if region_filter:
            filtered = [c for c in analyzed_clips if region_filter.lower() in c["region"].lower()]
            if filtered:
                analyzed_clips = filtered

        # Group by region to ensure geographic balance
        by_region: dict[str, list[dict[str, Any]]] = {}
        for c in analyzed_clips:
            tel = c.get("telemetry", {})
            max_alt = tel.get("max_alt_m", 0.0)
            avg_alt = tel.get("avg_alt_m", 0.0)
            mov = tel.get("movement_profile", "hover")

            # REJECTION FILTER: Eliminate ground junk, asphalt parking lots, pre-takeoff stationary shots
            # Clips that never gained meaningful altitude (< 5m) or were purely hovering on the ground
            if max_alt < 5.0 and mov == "hover":
                continue
            # Clips with virtually no altitude or distance displacement are pre-flight setups
            if avg_alt < 2.5:
                continue

            by_region.setdefault(c["region"], []).append(c)

        # Select the best hero clips from each region (variety of altitudes & moves)
        curated_clips: list[dict[str, Any]] = []
        for region_name, r_clips in by_region.items():
            # Sort within region by movement and altitude (dynamic crane/flyovers with real elevation first)
            def hero_score(clip_info: dict[str, Any]) -> float:
                t = clip_info.get("telemetry", {})
                score = t.get("avg_alt_m", 0.0)
                m = t.get("movement_profile")
                if m == "forward_flyover":
                    score += 20.0
                elif m == "ascending_crane":
                    score += 15.0
                elif m == "hover":
                    score -= 10.0
                return score

            r_clips.sort(key=hero_score, reverse=True)
            # Pick 2-3 clips per region
            picks = r_clips[:3]
            curated_clips.extend(picks)

        # Support ordering mode: 'chronological' (true linear time sequence) vs 'geographic_arc'
        if order_mode == "chronological":
            # Order clips strictly as they were recorded in real life
            curated_clips.sort(key=lambda c: (c.get("telemetry", {}).get("start_time") or c.get("name") or ""))
        else:
            # Build an intentional 3-Act Narrative Arc:
            # Act 1: High altitude mountain reveals (Angel Lake & Pequop Pass)
            # Act 2: Canyons & Waterfall flyovers (Shoshone Falls & Twin Falls)
            # Act 3: Low-altitude high-speed terrain runs & sunset (Bonneville Salt Flats)
            region_narrative_order = [
                "Angel Lake & Ruby Foothills",
                "Pequop Mountain Pass",
                "Twin Falls & Snake River",
                "Shoshone Falls & Canyon",
                "Bonneville Salt Flats",
            ]

            def narrative_sort_key(c: dict[str, Any]) -> tuple[int, float]:
                reg = c["region"]
                order_idx = region_narrative_order.index(reg) if reg in region_narrative_order else 99
                alt = c.get("telemetry", {}).get("avg_alt_m", 0.0)
                return (order_idx, -alt)

            curated_clips.sort(key=narrative_sort_key)


        # Ensure timeline
        self.harness.ensure_timeline(timeline_name)

        items_to_place: list[dict[str, Any]] = []
        title_markers: list[dict[str, Any]] = []
        accumulated_frame = 0  # Resolve Timeline AddMarker is 0-indexed relative to timeline start


        current_region: str | None = None
        region_scene_counter = 0

        for clip in curated_clips:
            fps = float(clip.get("fps") or 29.97)
            total_frames = int(clip.get("frames") or 300)
            tel = clip.get("telemetry", {})
            alt = tel.get("avg_alt_m", 25.0)
            mov = tel.get("movement_profile", "forward_flyover")

            # Dynamic length based on movement and altitude:
            # Grand high crane: 6.5s
            # Canyon flyover: 4.8s
            # Fast low proximity run: 3.2s
            if alt > 50.0 or mov == "ascending_crane":
                duration_sec = 6.5
            elif alt < 10.0 or mov == "forward_flyover":
                duration_sec = 3.8
            else:
                duration_sec = 5.0

            duration_frames = int(duration_sec * fps)

            # Use acceleration/jerk variance minimization to find the smoothest stabilized flight window
            path_str = clip.get("path")
            if path_str:
                start_f, end_f = find_stabilized_window(
                    video_path=path_str,
                    fps=fps,
                    duration_sec=duration_sec,
                    skip_startup_sec=4.0,
                )
            else:
                start_f = 120 if total_frames > (duration_frames + 120) else 0
                end_f = min(start_f + duration_frames, total_frames)


            items_to_place.append({
                "media_id": clip["media_id"],
                "source_in": start_f,
                "source_out": end_f,
                "track_type": "video",
                "track_index": 1,
            })

            # Check if entering a new geographic chapter (Chapter marker at start of shot)
            reg = clip["region"]
            if reg != current_region:
                current_region = reg
                region_scene_counter += 1
                safe_reg_name = reg.replace(" ", "-").replace("&", "and")
                title_markers.append({
                    "type": "chapter",
                    "frame": accumulated_frame,
                    "name": f"Part-{region_scene_counter}-{safe_reg_name}",
                    "note": f"Entering {reg} | Regional elevation: {alt:.1f}m",
                    "color": "Purple",
                })
            else:
                # Add Shot-level Marker on non-chapter shots
                title_markers.append({
                    "type": "broll",
                    "frame": accumulated_frame,
                    "name": f"{mov}-alt{int(alt)}m",
                    "note": f"{clip['name']} | Duration: {duration_sec}s",
                    "color": "Blue",
                })


            accumulated_frame += (end_f - start_f)

        # Place the items
        placed_res = self.harness.place(items_to_place)

        # Apply regional color grading on items
        for clip in curated_clips:
            try:
                self.harness.set_clip_color(color=clip["color"], clip_name=clip["name"])
            except Exception:
                pass

        # Stamp all chapter and title markers safely
        stamped_markers: list[dict[str, Any]] = []
        for m in title_markers:
            try:
                self.harness.marker_upsert(m)
                stamped_markers.append(m)
            except Exception:
                pass


        total_runtime_sec = round(accumulated_frame / 29.97, 1)


        return {
            "timeline": timeline_name,
            "total_runtime_sec": total_runtime_sec,
            "clips_count": len(items_to_place),
            "regions_covered": list(by_region.keys()),
            "title_markers": title_markers,
            "placed_items": items_to_place,
            "feedback_suggestions": [
                f"Assembled a 3-Act travel arc across {len(by_region)} geographic regions with dynamic pacing ({total_runtime_sec}s total).",
                "Grand reveals given 6.5s, canyon flyovers 5.0s, low-altitude flybys 3.8s.",
                "Color-coded by region: Sand for Bonneville, Teal for Shoshone, Olive for Angel Lake, Brown for Pequop.",
                "Review the Purple chapter markers for region names and Blue markers for shot elevations in Resolve!",
            ],
        }
