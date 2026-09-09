from video_harness.scripts import vh_runtime
from tests.fakes import FakeResolve


def test_ping_and_inspect():
    resolve = FakeResolve()
    ping = vh_runtime.dispatch(resolve, "ping")
    assert ping["ok"] is True
    assert ping["result"]["product"] == "DaVinci Resolve"
    snap = vh_runtime.dispatch(resolve, "inspect", {"media": "all"})
    assert snap["ok"] is True
    assert snap["result"]["project"]["name"] == "Show"
    assert snap["result"]["timeline"]["name"] == "Edit"
    assert snap["result"]["media"]["clip_count"] == 1


def test_place_and_typed_marker_upsert():
    resolve = FakeResolve()
    placed = vh_runtime.dispatch(
        resolve,
        "place",
        {
            "items": [
                {
                    "media_id": "media-a001",
                    "track_index": 2,
                    "record_frame": 87000,
                    "source_in": 0,
                    "source_out": 24,
                }
            ]
        },
    )
    assert placed["ok"] is True
    assert placed["result"]["count"] == 1
    assert placed["result"]["placed"][0]["start"] == 87000

    upsert = vh_runtime.dispatch(
        resolve,
        "marker_upsert",
        {
            "scope": "timeline",
            "frame": 86424,
            "color": "Cyan",
            "name": "beat",
            "note": "downbeat",
            "duration": 1,
            "payload": {
                "schema": "video-harness.marker/v1",
                "type": "beat",
                "id": "beat-1",
                "source": "test",
            },
        },
    )
    assert upsert["ok"] is True
    again = vh_runtime.dispatch(
        resolve,
        "marker_upsert",
        {
            "scope": "timeline",
            "frame": 86448,
            "color": "Cyan",
            "name": "beat",
            "duration": 1,
            "payload": {
                "schema": "video-harness.marker/v1",
                "type": "beat",
                "id": "beat-1",
                "source": "test",
            },
        },
    )
    assert again["result"]["markers"][0]["replaced"] is True
    queried = vh_runtime.dispatch(resolve, "markers_query", {"type": "beat"})
    assert queried["result"]["count"] == 1
    assert queried["result"]["markers"][0]["frame"] == 86448


def test_unknown_method():
    result = vh_runtime.dispatch(FakeResolve(), "nope", {})
    assert result["ok"] is False
    assert result["error"]["type"] == "UnknownMethod"
