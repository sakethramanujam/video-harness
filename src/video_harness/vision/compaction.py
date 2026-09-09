"""Change-only State Accumulator and temporal segment compaction.

Collapses redundant frames across time while preserving state deltas and keyframe markers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union
from .dhash import is_visually_static


@dataclass
class TemporalSegment:
    """Represents a temporally compacted video state segment."""

    start_frame: int
    end_frame: int
    start_pts: float
    end_pts: float
    representative_hash: int
    tags: List[str] = field(default_factory=list)
    summaries: List[str] = field(default_factory=list)
    frame_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert segment to standard dictionary representation."""
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_pts": round(self.start_pts, 4),
            "end_pts": round(self.end_pts, 4),
            "duration": round(max(0.0, self.end_pts - self.start_pts), 4),
            "frame_count": self.frame_count,
            "representative_hash": hex(self.representative_hash),
            "tags": sorted(list(set(self.tags))),
            "summary": " | ".join([s for s in self.summaries if s]) if self.summaries else "",
        }


class StateAccumulator:
    """Accumulates incoming frame states and compacts redundant frames into TemporalSegments.

    Uses perceptual dHash similarity threshold and semantic tags matching.
    If visually static or tags match previous active state: extends end_frame and end_pts.
    If delta detected: finalizes previous segment and initializes a new one.
    """

    def __init__(self, hash_threshold: int = 4, match_tags: bool = True):
        """
        :param hash_threshold: Max Hamming distance to treat frames as visually static.
        :param match_tags: If True, changes in tags force a state transition even if hash is static.
        """
        self.hash_threshold = hash_threshold
        self.match_tags = match_tags
        self._current_segment: Optional[TemporalSegment] = None
        self._finalized_segments: List[TemporalSegment] = []

    def process_frame(
        self,
        source_frame: int,
        pts_sec: float,
        dhash: int,
        tags: Optional[Sequence[str]] = None,
        summary: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Feed a frame into the accumulator.

        :param source_frame: Index or frame number.
        :param pts_sec: Timestamp in seconds.
        :param dhash: 64-bit perceptual hash integer.
        :param tags: Optional semantic tags for the frame.
        :param summary: Optional summary text/label for the frame.
        :return: Dict representation of finalized segment if a transition occurred, else None.
        """
        frame_tags = list(tags) if tags is not None else []
        frame_summary = summary.strip() if summary else ""

        if self._current_segment is None:
            # First frame, start new segment
            self._current_segment = TemporalSegment(
                start_frame=source_frame,
                end_frame=source_frame,
                start_pts=pts_sec,
                end_pts=pts_sec,
                representative_hash=dhash,
                tags=list(frame_tags),
                summaries=[frame_summary] if frame_summary else [],
                frame_count=1,
            )
            return None

        # Check visual static condition
        visual_static = is_visually_static(
            self._current_segment.representative_hash,
            dhash,
            threshold=self.hash_threshold,
        )

        # Check tags condition
        tags_match = True
        if self.match_tags and (frame_tags or self._current_segment.tags):
            tags_match = set(frame_tags) == set(self._current_segment.tags)

        if visual_static and tags_match:
            # Redundant frame - extend current segment
            self._current_segment.end_frame = source_frame
            self._current_segment.end_pts = pts_sec
            self._current_segment.frame_count += 1
            if frame_summary and frame_summary not in self._current_segment.summaries:
                self._current_segment.summaries.append(frame_summary)
            for t in frame_tags:
                if t not in self._current_segment.tags:
                    self._current_segment.tags.append(t)
            return None
        else:
            # Delta detected: finalize previous segment and open new one
            finalized = self._current_segment
            self._finalized_segments.append(finalized)

            self._current_segment = TemporalSegment(
                start_frame=source_frame,
                end_frame=source_frame,
                start_pts=pts_sec,
                end_pts=pts_sec,
                representative_hash=dhash,
                tags=list(frame_tags),
                summaries=[frame_summary] if frame_summary else [],
                frame_count=1,
            )
            return finalized.to_dict()

    def flush(self) -> List[Dict[str, Any]]:
        """Finalize any active segment and return the full list of compacted segments."""
        if self._current_segment is not None:
            self._finalized_segments.append(self._current_segment)
            self._current_segment = None

        return [seg.to_dict() for seg in self._finalized_segments]

    def reset(self) -> None:
        """Clear accumulator state."""
        self._current_segment = None
        self._finalized_segments.clear()
