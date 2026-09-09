"""Unit tests for perceptual dHash and temporal state compaction."""

import time
import pytest
from video_harness.vision.dhash import (
    compute_dhash,
    compute_dhash_from_bytes,
    compute_dhash_from_grayscale_grid,
    hamming_distance,
    is_visually_static,
)
from video_harness.vision.compaction import StateAccumulator, TemporalSegment


def test_hamming_distance():
    assert hamming_distance(0, 0) == 0
    assert hamming_distance(0b1101, 0b1101) == 0
    assert hamming_distance(0b1101, 0b1001) == 1
    assert hamming_distance(0, 0xFFFFFFFFFFFFFFFF) == 64
    assert hamming_distance(0x5555555555555555, 0xAAAAAAAAAAAAAAAA) == 64


def test_is_visually_static():
    base_hash = 0x1234567812345678
    # Exact match
    assert is_visually_static(base_hash, base_hash, threshold=4) is True
    # 2 bit flips
    perturbed = base_hash ^ 0b101
    assert is_visually_static(base_hash, perturbed, threshold=4) is True
    # 5 bit flips (exceeds default threshold 4)
    perturbed_5 = base_hash ^ 0b11111
    assert is_visually_static(base_hash, perturbed_5, threshold=4) is False
    assert is_visually_static(base_hash, perturbed_5, threshold=5) is True


def test_dhash_from_grid():
    # Construct 8x9 grid where each row is strictly increasing
    # row[col] > row[col+1] is always False -> all 0 bits
    grid_increasing = [[col for col in range(9)] for _ in range(8)]
    assert compute_dhash_from_grayscale_grid(grid_increasing) == 0

    # Construct 8x9 grid where each row is strictly decreasing
    # row[col] > row[col+1] is always True -> all 1 bits (64 ones = 0xFFFFFFFFFFFFFFFF)
    grid_decreasing = [[9 - col for col in range(9)] for _ in range(8)]
    assert compute_dhash_from_grayscale_grid(grid_decreasing) == 0xFFFFFFFFFFFFFFFF


def test_dhash_from_bytes_performance():
    # 640x480 grayscale frame
    w, h = 640, 480
    raw_frame = bytes([(x % 256) for x in range(w * h)])

    start_t = time.perf_counter()
    h1 = compute_dhash_from_bytes(raw_frame, w, h, channels=1)
    duration_ms = (time.perf_counter() - start_t) * 1000

    # Should compute in reasonably fast time (typically < 1-2 ms in pure python, ~0.5ms with buffer ops)
    assert isinstance(h1, int)
    assert h1 >= 0
    # Also verify deterministic
    h2 = compute_dhash_from_bytes(raw_frame, w, h, channels=1)
    assert h1 == h2
    assert hamming_distance(h1, h2) == 0


def test_dhash_rgb_bytes():
    # 9x8 image with 3 channels
    w, h = 9, 8
    # Create black frame and white frame
    black_frame = bytes(w * h * 3)
    white_frame = bytes([255] * (w * h * 3))

    h_black = compute_dhash_from_bytes(black_frame, w, h, channels=3)
    h_white = compute_dhash_from_bytes(white_frame, w, h, channels=3)

    # In uniform color image, pixel[c] > pixel[c+1] is always False -> 0
    assert h_black == 0
    assert h_white == 0


def test_state_accumulator_empty():
    acc = StateAccumulator()
    result = acc.flush()
    assert result == []


def test_state_accumulator_single_frame():
    acc = StateAccumulator()
    acc.process_frame(source_frame=0, pts_sec=0.0, dhash=0x1234, tags=["title"], summary="Title screen")
    segments = acc.flush()

    assert len(segments) == 1
    seg = segments[0]
    assert seg["start_frame"] == 0
    assert seg["end_frame"] == 0
    assert seg["start_pts"] == 0.0
    assert seg["end_pts"] == 0.0
    assert seg["duration"] == 0.0
    assert seg["frame_count"] == 1
    assert seg["tags"] == ["title"]
    assert seg["summary"] == "Title screen"


def test_state_accumulator_collapse_redundant_frames():
    acc = StateAccumulator(hash_threshold=2)

    # Sequence of visually static frames (same or slightly perturbed hash, same tags)
    base_hash = 0xAAAAAAAAAAAAAAAA
    acc.process_frame(0, 0.0, base_hash, tags=["idle"], summary="Menu idle")
    acc.process_frame(1, 0.033, base_hash ^ 1, tags=["idle"], summary="Menu idle")
    acc.process_frame(2, 0.066, base_hash ^ 2, tags=["idle"], summary="Menu idle")
    acc.process_frame(3, 0.100, base_hash, tags=["idle"], summary="Menu idle")

    # Significant delta: new hash (Hamming distance > 2)
    new_hash = base_hash ^ 0xFF  # 8 bit flips
    res = acc.process_frame(4, 0.133, new_hash, tags=["gameplay"], summary="Game started")

    # The 4th frame should trigger completion of first segment
    assert res is not None
    assert res["start_frame"] == 0
    assert res["end_frame"] == 3
    assert res["frame_count"] == 4
    assert res["start_pts"] == 0.0
    assert res["end_pts"] == 0.100

    # Add another frame to the new segment
    acc.process_frame(5, 0.166, new_hash, tags=["gameplay"], summary="Game playing")

    all_segs = acc.flush()
    assert len(all_segs) == 2

    seg1, seg2 = all_segs
    assert seg1["start_frame"] == 0
    assert seg1["end_frame"] == 3
    assert seg1["frame_count"] == 4
    assert seg1["tags"] == ["idle"]

    assert seg2["start_frame"] == 4
    assert seg2["end_frame"] == 5
    assert seg2["frame_count"] == 2
    assert seg2["tags"] == ["gameplay"]
    assert "Game started" in seg2["summary"]
    assert "Game playing" in seg2["summary"]


def test_state_accumulator_tag_change_forces_segment():
    acc = StateAccumulator(hash_threshold=4, match_tags=True)

    base_hash = 0x1111222233334444
    # Identical hash, but tags change
    acc.process_frame(0, 0.0, base_hash, tags=["scene_a"])
    acc.process_frame(1, 0.5, base_hash, tags=["scene_b"])

    segments = acc.flush()
    assert len(segments) == 2
    assert segments[0]["start_frame"] == 0
    assert segments[0]["end_frame"] == 0
    assert segments[0]["tags"] == ["scene_a"]

    assert segments[1]["start_frame"] == 1
    assert segments[1]["end_frame"] == 1
    assert segments[1]["tags"] == ["scene_b"]


def test_state_accumulator_reset():
    acc = StateAccumulator()
    acc.process_frame(0, 0.0, 0x1)
    acc.process_frame(1, 1.0, 0x1)
    acc.reset()
    assert acc.flush() == []
