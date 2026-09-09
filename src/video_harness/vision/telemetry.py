"""Telemetry and subtitle metadata extractor for drone and camera footage.

Parses DJI and action camera companion .SRT files containing:
- ISO, Shutter speed, F-number, EV, Color profile, Focal length
- GPS Latitude and Longitude
- Relative Altitude (rel_alt) and Absolute Altitude (abs_alt)
- Real-world ISO timestamps
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TelemetryFrame:
    index: int
    time_start: str
    time_end: str
    iso_timestamp: str | None
    latitude: float | None
    longitude: float | None
    rel_alt: float | None
    abs_alt: float | None
    iso: int | None
    shutter: str | None
    focal_len: float | None


def find_companion_srt(video_path: str | Path) -> Path | None:
    """Find companion .SRT file for a given video path."""
    p = Path(video_path)
    # Check exact case and lowercase/uppercase variants
    candidates = [
        p.with_suffix(".SRT"),
        p.with_suffix(".srt"),
        p.with_suffix(".Srt"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def parse_telemetry_srt(srt_path: str | Path) -> dict[str, Any]:
    """Parse telemetry from .SRT companion file.

    Returns summary metadata and key trajectory points (start, mid, end).
    """
    path = Path(srt_path)
    if not path.exists():
        return {}

    content = path.read_text(encoding="utf-8", errors="ignore")
    blocks = content.strip().split("\n\n")

    latitudes: list[float] = []
    longitudes: list[float] = []
    altitudes: list[float] = []
    timestamps: list[str] = []

    # Regex patterns for telemetry fields
    re_lat = re.compile(r"latitude:\s*([\-0-9\.]+)")
    re_lon = re.compile(r"longitude:\s*([\-0-9\.]+)")
    re_alt = re.compile(r"rel_alt:\s*([\-0-9\.]+)")
    re_abs_alt = re.compile(r"abs_alt:\s*([\-0-9\.]+)")
    re_iso = re.compile(r"\[iso:\s*([0-9]+)\]")
    re_shutter = re.compile(r"\[shutter:\s*([^\]]+)\]")
    re_time = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+)")

    first_time: str | None = None
    last_time: str | None = None

    for block in blocks:
        m_lat = re_lat.search(block)
        m_lon = re_lon.search(block)
        m_alt = re_alt.search(block)
        m_time = re_time.search(block)

        if m_lat and m_lon:
            latitudes.append(float(m_lat.group(1)))
            longitudes.append(float(m_lon.group(1)))
        if m_alt:
            altitudes.append(float(m_alt.group(1)))
        if m_time:
            t = m_time.group(1)
            if not first_time:
                first_time = t
            last_time = t

    if not latitudes and not altitudes:
        return {}

    min_alt = min(altitudes) if altitudes else 0.0
    max_alt = max(altitudes) if altitudes else 0.0
    avg_alt = round(sum(altitudes) / len(altitudes), 1) if altitudes else 0.0
    start_alt = altitudes[0] if altitudes else 0.0
    end_alt = altitudes[-1] if altitudes else 0.0

    # Classify movement flight pattern
    movement = "hover"
    if (end_alt - start_alt) > 15.0:
        movement = "ascending_crane"
    elif (start_alt - end_alt) > 15.0:
        movement = "descending_crane"
    elif len(latitudes) > 10:
        # Distance delta between start and end
        delta_lat = abs(latitudes[-1] - latitudes[0])
        delta_lon = abs(longitudes[-1] - longitudes[0])
        if (delta_lat + delta_lon) > 0.0005:
            movement = "forward_flyover"

    return {
        "start_time": first_time,
        "end_time": last_time,
        "start_gps": [latitudes[0], longitudes[0]] if latitudes else None,
        "end_gps": [latitudes[-1], longitudes[-1]] if latitudes else None,
        "start_alt_m": start_alt,
        "end_alt_m": end_alt,
        "min_alt_m": min_alt,
        "max_alt_m": max_alt,
        "avg_alt_m": avg_alt,
        "movement_profile": movement,
    }


def find_stabilized_window(
    video_path: str | Path,
    fps: float,
    duration_sec: float,
    skip_startup_sec: float = 4.0,
) -> tuple[int, int]:
    """Find the smoothest flight window by minimizing acceleration variance (jerk).

    Skips the initial startup frames to eliminate gimbal motors settling and takeoff jitter.
    """
    import math

    target_frames = int(round(duration_sec * fps))
    skip_frames = int(round(skip_startup_sec * fps))
    srt_path = find_companion_srt(video_path)

    if not srt_path:
        return (skip_frames, skip_frames + target_frames)

    content = Path(srt_path).read_text(encoding="utf-8", errors="ignore")
    re_lat = re.compile(r"latitude:\s*([\-0-9\.]+)")
    re_lon = re.compile(r"longitude:\s*([\-0-9\.]+)")
    re_alt = re.compile(r"rel_alt:\s*([\-0-9\.]+)")

    points: list[tuple[float, float, float]] = []
    for b in content.strip().split("\n\n"):
        m_lat = re_lat.search(b)
        m_lon = re_lon.search(b)
        m_alt = re_alt.search(b)
        if m_lat and m_lon and m_alt:
            points.append((float(m_lat.group(1)), float(m_lon.group(1)), float(m_alt.group(1))))

    total_samples = len(points)
    if total_samples <= (target_frames + skip_frames):
        start = min(skip_frames, max(0, total_samples - target_frames))
        return (start, min(total_samples - 1, start + target_frames))

    # Calculate frame-to-frame delta displacements
    velocities: list[float] = []
    for i in range(1, total_samples):
        dy = (points[i][0] - points[i - 1][0]) * 111000
        dx = (points[i][1] - points[i - 1][1]) * 84000
        dz = points[i][2] - points[i - 1][2]
        velocities.append(math.sqrt(dx**2 + dy**2 + dz**2))

    best_start = skip_frames
    min_variance = float("inf")
    max_search = len(velocities) - target_frames - 15

    for s in range(skip_frames, max(skip_frames + 1, max_search), 15):
        window = velocities[s : s + target_frames]
        if not window:
            continue
        mean = sum(window) / len(window)
        var = sum((v - mean) ** 2 for v in window) / len(window)
        if var < min_variance:
            min_variance = var
            best_start = s

    return (best_start, best_start + target_frames)

