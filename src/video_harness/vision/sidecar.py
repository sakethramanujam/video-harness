"""Compact JSONL sidecar storage and retrieval for video semantic context.

Stores segments under:
  <config_dir>/describe/<sanitized_media_id>.jsonl
Each file starts with an optional header line `{"_schema": "video-harness.sidecar/v1", "media_id": ...}`
followed by compact JSON records for each TemporalSegment.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from video_harness.paths import config_dir


def _sanitize_media_id(media_id: str) -> str:
    """Sanitize media_id to safe filename characters."""
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", media_id)


class SidecarIndex:
    """Manages reading, writing, and searching compact video context sidecar files."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (config_dir() / "describe")

    def _get_path(self, media_id: str) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir / f"{_sanitize_media_id(media_id)}.jsonl"

    def save_segments(
        self,
        media_id: str,
        segments: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Write compact JSONL sidecar file.

        Header contains metadata (fps, file path, resolution, total duration).
        Subsequent lines are individual compacted temporal segments.
        """
        path = self._get_path(media_id)
        header = {
            "_schema": "video-harness.sidecar/v1",
            "media_id": media_id,
            "metadata": metadata or {},
            "segment_count": len(segments),
        }
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(header) + "\n")
            for seg in segments:
                f.write(json.dumps(seg) + "\n")
        return path

    def load_segments(self, media_id: str) -> list[dict[str, Any]]:
        """Load segments from sidecar file. Skips header if present."""
        path = self._get_path(media_id)
        if not path.exists():
            return []

        segments: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if "_schema" in data:
                    continue
                segments.append(data)
        return segments

    def load_metadata(self, media_id: str) -> dict[str, Any]:
        """Load metadata header from sidecar file."""
        path = self._get_path(media_id)
        if not path.exists():
            return {}

        with open(path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if first_line:
                data = json.loads(first_line)
                if "_schema" in data:
                    return data.get("metadata", {})
        return {}

    def search(
        self,
        media_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search sidecar segments for query matches.

        Scores based on keyword matches across tags, shot types, and summary descriptions.
        """
        segments = self.load_segments(media_id)
        if not segments:
            return []

        q_terms = [t.lower() for t in query.split() if t.strip()]
        if not q_terms:
            return segments[:top_k]

        scored: list[tuple[float, dict[str, Any]]] = []
        for seg in segments:
            score = 0.0
            tags = [str(t).lower() for t in seg.get("tags", [])]
            summary = str(seg.get("summary", "")).lower()
            shot = str(seg.get("shot", "")).lower()

            for term in q_terms:
                if any(term == tag for tag in tags):
                    score += 3.0
                elif any(term in tag for tag in tags):
                    score += 1.5
                if term in summary:
                    score += 2.0
                if term in shot:
                    score += 1.0

            if score > 0:
                seg_result = dict(seg)
                seg_result["relevance_score"] = score
                scored.append((score, seg_result))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
