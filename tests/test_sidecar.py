from pathlib import Path
from video_harness.vision.sidecar import SidecarIndex


def test_sidecar_save_load_search(tmp_path: Path):
    index = SidecarIndex(base_dir=tmp_path)
    media_id = "clip_101"
    segments = [
        {
            "start_frame": 0,
            "end_frame": 72,
            "start_pts": 0.0,
            "end_pts": 3.0,
            "tags": ["host", "talking", "studio"],
            "shot": "medium",
            "summary": "Host introducing the tech review",
        },
        {
            "start_frame": 73,
            "end_frame": 180,
            "start_pts": 3.04,
            "end_pts": 7.5,
            "tags": ["broll", "unboxing", "product"],
            "shot": "close-up",
            "summary": "Close-up macro of opening the box and unwrapping phone",
        },
    ]
    metadata = {"fps": 24.0, "path": "/Movies/clip1.mov"}

    saved_path = index.save_segments(media_id, segments, metadata)
    assert saved_path.exists()

    loaded = index.load_segments(media_id)
    assert len(loaded) == 2
    assert loaded[0]["start_frame"] == 0
    assert loaded[1]["tags"] == ["broll", "unboxing", "product"]

    loaded_meta = index.load_metadata(media_id)
    assert loaded_meta["fps"] == 24.0

    # Test search by tag
    results = index.search(media_id, "unboxing")
    assert len(results) == 1
    assert results[0]["start_frame"] == 73

    # Test search by summary keyword
    results = index.search(media_id, "introducing")
    assert len(results) == 1
    assert results[0]["start_frame"] == 0

    # Test search non-matching
    results = index.search(media_id, "explosion")
    assert len(results) == 0
