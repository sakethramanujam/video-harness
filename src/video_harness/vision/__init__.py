"""Vision processing, perceptual hashing, and temporal compaction."""

from .dhash import compute_dhash, compute_dhash_from_bytes, hamming_distance, is_visually_static
from .compaction import StateAccumulator, TemporalSegment
from .sidecar import SidecarIndex

__all__ = [
    "compute_dhash",
    "compute_dhash_from_bytes",
    "hamming_distance",
    "is_visually_static",
    "StateAccumulator",
    "TemporalSegment",
    "SidecarIndex",
]

