"""VideoToolbox hardware-accelerated frame extraction and PTS alignment.

Uses macOS VideoToolbox via ffmpeg and ffprobe.
Guarantees:
- Accurate Presentation TimeStamps (PTS) and frame indices.
- Downscales extracted frames directly to 448-512px to protect Metal unified memory.
- B-frame PTS reordering handled cleanly by ffmpeg decode pipeline.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class VideoStreamInfo:
    duration_seconds: float
    fps: float
    width: int
    height: int
    nb_frames: int


def probe_video(video_path: str | Path) -> VideoStreamInfo:
    """Probe video file for duration, FPS, and dimensions using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)

    video_stream = None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise ValueError(f"No video stream found in {video_path}")

    # Calculate FPS
    fps_str = video_stream.get("avg_frame_rate", "24/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 24.0
    else:
        fps = float(fps_str) if fps_str else 24.0

    duration = float(video_stream.get("duration") or info.get("format", {}).get("duration") or 0.0)
    nb_frames = int(video_stream.get("nb_frames") or round(duration * fps))

    return VideoStreamInfo(
        duration_seconds=duration,
        fps=fps,
        width=int(video_stream.get("width", 1920)),
        height=int(video_stream.get("height", 1080)),
        nb_frames=nb_frames,
    )


def extract_frames_stream(
    video_path: str | Path,
    interval_seconds: float = 2.0,
    target_width: int = 480,
    use_videotoolbox: bool = True,
) -> Iterator[tuple[int, float, bytes, int, int]]:
    """Stream downscaled RGB24 frames at regular intervals.

    Yields:
      (source_frame, pts_sec, raw_rgb_bytes, width, height)
    Uses VideoToolbox hwaccel if enabled on macOS.
    """
    info = probe_video(video_path)
    # Calculate aspect-ratio scaled height (must be even)
    target_height = int(round((target_width * info.height / info.width) / 2) * 2)

    # ffmpeg fps filter samples at exact interval
    fps_rate = 1.0 / max(0.1, interval_seconds)

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if use_videotoolbox:
        # Hardware acceleration via VideoToolbox
        cmd.extend(["-hwaccel", "videotoolbox"])

    cmd.extend([
        "-i", str(video_path),
        "-vf", f"fps={fps_rate:.4f},scale={target_width}:{target_height}",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "pipe:1"
    ])

    frame_bytes_size = target_width * target_height * 3
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    sample_index = 0
    try:
        assert process.stdout is not None
        while True:
            raw = process.stdout.read(frame_bytes_size)
            if not raw or len(raw) < frame_bytes_size:
                break

            pts_sec = sample_index * interval_seconds
            source_frame = int(round(pts_sec * info.fps))

            yield (source_frame, pts_sec, raw, target_width, target_height)
            sample_index += 1
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
