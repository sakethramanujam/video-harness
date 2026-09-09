from video_harness.mark import event_to_upsert, events_from_clip_metadata
from video_harness.registry import TypeRegistry


def test_timeline_beat_uses_registry_color():
    registry = TypeRegistry.load()
    timeline = {"fps": "24", "start_frame": 86400}
    spec = event_to_upsert(
        {"type": "beat", "at": "01:00:02:00", "id": "beat-1"},
        registry,
        timeline=timeline,
    )
    assert spec["scope"] == "timeline"
    assert spec["color"] == "Cyan"
    assert spec["frame"] == 86400 + 48
    assert spec["payload"]["id"] == "beat-1"
    assert spec["payload"]["type"] == "beat"
    assert spec["duration"] == 1


def test_item_marker_is_clip_relative():
    registry = TypeRegistry.load()
    timeline = {
        "fps": "24",
        "start_frame": 86400,
        "tracks": [
            {
                "type": "video",
                "index": 1,
                "items": [
                    {
                        "unique_id": "item-1",
                        "media_id": "media-a001",
                        "name": "A001.mov",
                        "start": 86400,
                        "source_start": 12,
                        "fps": "24",
                    }
                ],
            }
        ],
    }
    spec = event_to_upsert(
        {"type": "dialogue", "at": 20, "media_id": "media-a001", "id": "dlg-1", "duration_frames": 10},
        registry,
        timeline=timeline,
    )
    assert spec["scope"] == "item"
    assert spec["unique_id"] == "item-1"
    assert spec["frame"] == 8  # 20 - source_start 12
    assert spec["duration"] == 10
    assert spec["color"] == "Green"


def test_events_from_clip_metadata():
    clips = [{"media_id": "m1", "name": "A", "metadata": {"Keywords": "hero"}}]
    events = events_from_clip_metadata(clips)
    assert events[0]["type"] == "keyword"
    assert events[0]["scope"] == "clip"
    assert "hero" in events[0]["note"]
