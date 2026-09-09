from __future__ import annotations

import re
from typing import Any

_TC_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})[:;](\d{2})$")


def parse_fps(value: Any, default: float = 24.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith(" i") or text.endswith(" I"):
        text = text[:-2].strip()
    try:
        return float(text)
    except ValueError:
        return default


def frames_to_timecode(frame: float | int, fps: float) -> str:
    fps = fps or 24.0
    total = int(round(float(frame)))
    if total < 0:
        total = 0
    ff = int(round(fps)) or 24
    frames = total % ff
    seconds_total = total // ff
    seconds = seconds_total % 60
    minutes_total = seconds_total // 60
    minutes = minutes_total % 60
    hours = minutes_total // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def timecode_to_frames(timecode: str, fps: float) -> float:
    match = _TC_RE.match(timecode.strip())
    if not match:
        raise ValueError(f"Not a timecode: {timecode!r}")
    hours, minutes, seconds, frames = (int(p) for p in match.groups())
    ff = parse_fps(fps)
    return float(((hours * 60 + minutes) * 60 + seconds) * ff + frames)


def coerce_frame(value: Any, fps: float) -> float:
    if isinstance(value, bool):
        raise ValueError("frame cannot be bool")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if _TC_RE.match(text):
        return timecode_to_frames(text, fps)
    return float(text)
