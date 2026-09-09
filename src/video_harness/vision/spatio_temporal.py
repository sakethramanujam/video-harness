"""Spatio-temporal scene understanding and visual composition analyzer.

Pure standard library + raw RGB byte processing. Computes:
1. Spatial Composition:
   - Dynamic luminance & contrast distribution (identifies blown out / pitch black / muddy footage).
   - High-frequency edge gradient energy via Sobel/Laplacian proxy (distinguishes texture-rich scenes vs blank asphalt/sky/mud).
   - Spatial color variance across quadrants (detects focal subjects vs uniform textures).

2. Temporal Dynamics:
   - Temporal motion vectors / frame difference magnitude (distinguishes static/locked tripod, smooth pan/crane, vs erratic jitter).
   - Motion stability ratio (stability vs erratic shake).

3. Semantic Scene Categorization:
   - shot_type: wide_establishing, medium_scenic, close_detail, or uncomposed_dead_frame.
   - dynamics: locked_static, smooth_tracking, high_speed_dynamic, or jittery_unstable.
   - visual_quality_score: 0.0 to 10.0 scale reflecting composition clarity and stability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FrameVisualMetrics:
    pts_sec: float
    source_frame: int
    mean_luminance: float       # 0 - 255
    contrast_std: float         # Standard deviation of luminance
    edge_energy: float          # High-frequency spatial gradients (detail/composition)
    quadrant_balance: float     # Spatial distribution across four quadrants (0.0 - 1.0)
    visual_clarity_score: float # 0.0 - 10.0 score based on contrast, lighting, and detail


@dataclass
class SpatioTemporalSceneInfo:
    start_frame: int
    end_frame: int
    start_pts: float
    end_pts: float
    duration_sec: float
    shot_type: str              # wide_establishing, medium_scenic, close_detail, or uncomposed_dead_frame
    dynamics: str               # locked_static, smooth_tracking, high_speed_dynamic, jittery_unstable
    motion_magnitude: float     # Average temporal pixel displacement
    motion_stability: float     # 1.0 = smooth/stable, 0.0 = erratic jerk
    quality_score: float        # 0.0 - 10.0 composite visual score
    is_usable: bool             # Quality gate flag: False for blank, jittery, or dead frames
    tags: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_pts": round(self.start_pts, 3),
            "end_pts": round(self.end_pts, 3),
            "duration_sec": round(self.duration_sec, 2),
            "shot_type": self.shot_type,
            "dynamics": self.dynamics,
            "motion_magnitude": round(self.motion_magnitude, 2),
            "motion_stability": round(self.motion_stability, 2),
            "quality_score": round(self.quality_score, 1),
            "is_usable": self.is_usable,
            "tags": sorted(list(set(self.tags))),
            "summary": self.summary,
        }


def analyze_spatial_frame(
    raw_rgb: bytes,
    width: int,
    height: int,
    pts_sec: float = 0.0,
    source_frame: int = 0,
) -> FrameVisualMetrics:
    """Analyze spatial composition, lighting, contrast, and edge detail of a single RGB24 frame."""
    total_pixels = width * height
    if total_pixels == 0 or len(raw_rgb) < total_pixels * 3:
        return FrameVisualMetrics(
            pts_sec=pts_sec,
            source_frame=source_frame,
            mean_luminance=0.0,
            contrast_std=0.0,
            edge_energy=0.0,
            quadrant_balance=0.0,
            visual_clarity_score=0.0,
        )

    # Subsample step to process frame rapidly (sample ~8,000 pixels max per frame)
    step = max(1, int(math.sqrt(total_pixels / 8000)))

    lums: list[float] = []
    # 4 Quadrants: Q0: Top-Left, Q1: Top-Right, Q2: Bottom-Left, Q3: Bottom-Right
    quad_lums: list[list[float]] = [[], [], [], []]
    half_w = width // 2
    half_h = height // 2

    # High frequency edge gradients (horizontal & vertical difference)
    edge_diffs: list[float] = []

    stride = width * 3
    for y in range(0, height - step, step):
        row_offset = y * stride
        next_row_offset = (y + step) * stride
        is_bottom = y >= half_h

        for x in range(0, width - step, step):
            idx = row_offset + x * 3
            r = raw_rgb[idx]
            g = raw_rgb[idx + 1]
            b = raw_rgb[idx + 2]
            # Standard Rec.709 perceived luminance
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            lums.append(lum)

            # Assign to quadrant
            is_right = x >= half_w
            q_idx = (2 if is_bottom else 0) + (1 if is_right else 0)
            quad_lums[q_idx].append(lum)

            # Spatial gradient: difference with right pixel and bottom pixel
            right_idx = row_offset + (x + step) * 3
            down_idx = next_row_offset + x * 3

            r_right = raw_rgb[right_idx]
            g_right = raw_rgb[right_idx + 1]
            b_right = raw_rgb[right_idx + 2]
            lum_right = 0.2126 * r_right + 0.7152 * g_right + 0.0722 * b_right

            r_down = raw_rgb[down_idx]
            g_down = raw_rgb[down_idx + 1]
            b_down = raw_rgb[down_idx + 2]
            lum_down = 0.2126 * r_down + 0.7152 * g_down + 0.0722 * b_down

            dx = abs(lum - lum_right)
            dy = abs(lum - lum_down)
            edge_diffs.append(dx + dy)

    n = len(lums)
    if n == 0:
        mean_lum = 0.0
        contrast_std = 0.0
    else:
        mean_lum = sum(lums) / n
        variance = sum((l - mean_lum) ** 2 for l in lums) / n
        contrast_std = math.sqrt(variance)

    mean_edge = (sum(edge_diffs) / len(edge_diffs)) if edge_diffs else 0.0

    # Quadrant balance: check if illumination/contrast is spread or focused
    quad_means = [
        (sum(quad_lums[i]) / len(quad_lums[i])) if quad_lums[i] else 0.0
        for i in range(4)
    ]
    avg_quad = sum(quad_means) / 4.0
    if avg_quad > 0:
        quad_dispersion = sum(abs(qm - avg_quad) for qm in quad_means) / (4.0 * avg_quad)
        quadrant_balance = max(0.0, 1.0 - quad_dispersion)
    else:
        quadrant_balance = 0.0

    # Visual clarity scoring (0 - 10)
    clarity = 5.0
    # Contrast bonus / penalty
    if 25.0 <= contrast_std <= 85.0:
        clarity += 2.0
    elif contrast_std < 12.0:
        clarity -= 3.0  # Washed out / flat / muddy

    # Detail / edge richness
    if mean_edge > 12.0:
        clarity += 2.0
    elif mean_edge < 3.5:
        clarity -= 2.5  # Out of focus / featureless asphalt or blank sky

    # Exposure bounds
    if 40.0 <= mean_lum <= 215.0:
        clarity += 1.0
    else:
        clarity -= 2.0  # Blown out or pitch black

    clarity = max(0.0, min(10.0, clarity))

    return FrameVisualMetrics(
        pts_sec=pts_sec,
        source_frame=source_frame,
        mean_luminance=round(mean_lum, 2),
        contrast_std=round(contrast_std, 2),
        edge_energy=round(mean_edge, 2),
        quadrant_balance=round(quadrant_balance, 2),
        visual_clarity_score=round(clarity, 1),
    )


class SpatioTemporalSceneAnalyzer:
    """Accumulates temporal frame metrics and produces spatio-temporal scene interpretations."""

    def __init__(self, quality_threshold: float = 4.5):
        self.quality_threshold = quality_threshold
        self._prev_frame_bytes: bytes | None = None
        self._window_metrics: list[FrameVisualMetrics] = []
        self._frame_motions: list[float] = []

    def process_frame(
        self,
        raw_rgb: bytes,
        width: int,
        height: int,
        pts_sec: float,
        source_frame: int,
    ) -> tuple[FrameVisualMetrics, float]:
        """Processes frame, returning (metrics, motion_from_previous)."""
        metrics = analyze_spatial_frame(raw_rgb, width, height, pts_sec=pts_sec, source_frame=source_frame)
        self._window_metrics.append(metrics)

        motion = 0.0
        if self._prev_frame_bytes is not None and len(self._prev_frame_bytes) == len(raw_rgb):
            step = max(1, len(raw_rgb) // 8000)
            diffs = [
                abs(raw_rgb[i] - self._prev_frame_bytes[i])
                for i in range(0, len(raw_rgb), step)
            ]
            motion = (sum(diffs) / len(diffs)) if diffs else 0.0

        self._frame_motions.append(motion)
        self._prev_frame_bytes = raw_rgb
        return metrics, motion

    def synthesize_scene(
        self,
        start_frame: int,
        end_frame: int,
        start_pts: float,
        end_pts: float,
        external_tags: list[str] | None = None,
        external_summary: str | None = None,
        camera_metadata: dict[str, Any] | None = None,
    ) -> SpatioTemporalSceneInfo:
        """Synthesize spatio-temporal scene intelligence from collected metrics."""
        duration = max(0.1, end_pts - start_pts)

        if not self._window_metrics:
            return SpatioTemporalSceneInfo(
                start_frame=start_frame,
                end_frame=end_frame,
                start_pts=start_pts,
                end_pts=end_pts,
                duration_sec=duration,
                shot_type="uncomposed_dead_frame",
                dynamics="locked_static",
                motion_magnitude=0.0,
                motion_stability=1.0,
                quality_score=0.0,
                is_usable=False,
                tags=["low_quality", "dead_frame"],
                summary="Insufficient visual data",
            )

        avg_clarity = sum(m.visual_clarity_score for m in self._window_metrics) / len(self._window_metrics)
        avg_edge = sum(m.edge_energy for m in self._window_metrics) / len(self._window_metrics)
        avg_contrast = sum(m.contrast_std for m in self._window_metrics) / len(self._window_metrics)

        # Motion analysis
        valid_motions = [m for m in self._frame_motions if m > 0.0]
        avg_motion = (sum(valid_motions) / len(valid_motions)) if valid_motions else 0.0

        if len(valid_motions) > 1:
            m_mean = avg_motion
            m_var = sum((m - m_mean) ** 2 for m in valid_motions) / len(valid_motions)
            stability = max(0.0, 1.0 - (math.sqrt(m_var) / max(5.0, m_mean)))
        else:
            stability = 1.0

        # Categorize dynamics
        if avg_motion < 1.5:
            dynamics = "locked_static"
        elif stability > 0.60 and avg_motion < 30.0:
            dynamics = "smooth_tracking"
        elif stability <= 0.35 and avg_motion > 15.0:
            dynamics = "jittery_unstable"
        else:
            dynamics = "high_speed_dynamic"

        # Categorize shot composition
        if avg_clarity < 3.5 or avg_edge < 3.5:
            shot_type = "uncomposed_dead_frame"
        elif avg_edge > 12.0 and avg_contrast > 35.0:
            shot_type = "wide_establishing"
        elif avg_edge > 7.5:
            shot_type = "medium_scenic"
        else:
            shot_type = "close_detail"

        # Check usability quality gate
        is_usable = (
            avg_clarity >= self.quality_threshold
            and dynamics != "jittery_unstable"
            and shot_type != "uncomposed_dead_frame"
        )

        # Generate contextual tags
        tags = list(external_tags or [])
        tags.extend([shot_type, dynamics])
        if avg_clarity >= 7.5:
            tags.append("hero_composition")
        elif avg_clarity < 4.0:
            tags.append("low_contrast_or_flat")

        # Synthesize semantic summary
        summary_parts = []
        if external_summary:
            summary_parts.append(external_summary)
        summary_parts.append(f"{shot_type.replace('_', ' ').capitalize()} with {dynamics.replace('_', ' ')}")
        summary_parts.append(f"visual quality {avg_clarity:.1f}/10")
        if camera_metadata:
            if "movement_profile" in camera_metadata:
                summary_parts.append(f"motion {camera_metadata['movement_profile']}")
            if "avg_alt_m" in camera_metadata:
                summary_parts.append(f"alt {camera_metadata['avg_alt_m']}m")

        summary = " | ".join(summary_parts)

        # Clear window
        self._window_metrics.clear()
        self._frame_motions.clear()

        return SpatioTemporalSceneInfo(
            start_frame=start_frame,
            end_frame=end_frame,
            start_pts=start_pts,
            end_pts=end_pts,
            duration_sec=duration,
            shot_type=shot_type,
            dynamics=dynamics,
            motion_magnitude=avg_motion,
            motion_stability=stability,
            quality_score=avg_clarity,
            is_usable=is_usable,
            tags=tags,
            summary=summary,
        )
