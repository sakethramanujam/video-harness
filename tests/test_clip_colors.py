import json

import pytest

from video_harness.bridge_client import loads_rpc_json
from video_harness.clip_colors import normalize_clip_color
from video_harness.errors import PlacementError
from video_harness.scripts import vh_runtime
from tests.fakes import FakeResolve


def test_normalize_passthrough_and_aliases():
    assert normalize_clip_color("Green") == "Green"
    assert normalize_clip_color("teal") == "Teal"
    assert normalize_clip_color("Cyan") == "Teal"
    assert normalize_clip_color("Mint") == "Lime"
    assert normalize_clip_color("Red") == "Violet"
    assert normalize_clip_color("") == ""
    with pytest.raises(PlacementError):
        normalize_clip_color("Chartreuse")


def test_loads_rpc_json_allows_control_characters():
    raw = '{"ok": true, "id": "1", "result": {"name": "clip' + chr(1) + 'x"}}'
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    body = loads_rpc_json(raw)
    assert body["ok"] is True
    assert "clip" in body["result"]["name"]


def test_set_clip_color_maps_cyan_and_rejects_unknown():
    resolve = FakeResolve()
    colored = vh_runtime.dispatch(resolve, "set_clip_color", {"color": "Cyan"})
    assert colored["ok"] is True
    assert colored["result"]["changed"][0]["color"] == "Teal"
    assert colored["result"]["changed"][0]["success"] is True
    item = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline().video[0][0]
    assert item.GetClipColor() == "Teal"

    bad = vh_runtime.dispatch(resolve, "set_clip_color", {"color": "Chartreuse"})
    assert bad["ok"] is False
    assert bad["error"]["type"] == "PlacementError"


def test_inspect_media_none_skips_clips():
    resolve = FakeResolve()
    snap = vh_runtime.dispatch(resolve, "inspect", {"media": "none"})
    assert snap["ok"] is True
    assert snap["result"]["timeline"]["name"] == "Edit"
    assert snap["result"]["media"]["clip_count"] == 0
    assert snap["result"]["media"]["clips"] == []
    assert snap["result"]["app"]["methods"]
    assert "set_clip_color" in snap["result"]["app"]["methods"]
