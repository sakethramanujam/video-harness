from video_harness.harness import Harness
from video_harness.session import Session
from video_harness.vision.assistant import EditAssistant
from video_harness.vision.sidecar import SidecarIndex


class MockImpl:
    def __init__(self):
        self.calls = []

    def call(self, method: str, params: dict | None = None):
        self.calls.append((method, params or {}))
        if method == "ensure_timeline":
            return {"timeline": {"name": (params or {}).get("name")}}
        if method == "place":
            return {"placed": (params or {}).get("items", []), "count": len((params or {}).get("items", []))}
        if method == "set_clip_color":
            return {"colored": 1}
        return {}


def test_edit_assistant_draft_cut_with_sidecar(tmp_path: Path):
    sidecar = SidecarIndex(base_dir=tmp_path)
    media_id = "test_clip"
    segments = [
        {"start_frame": 0, "end_frame": 100, "start_pts": 0.0, "end_pts": 4.16, "tags": ["host", "talking"], "summary": "Host talk"},
        {"start_frame": 101, "end_frame": 250, "start_pts": 4.2, "end_pts": 10.4, "tags": ["action", "broll"], "summary": "Action broll"},
    ]
    sidecar.save_segments(media_id, segments, metadata={"fps": 24.0})

    mock_impl = MockImpl()
    session = Session("bridge", mock_impl)
    harness = Harness(session)
    assistant = EditAssistant(harness, sidecar_index=sidecar)


    draft = assistant.generate_draft_cut(
        timeline_name="First_Pass_Timeline",
        media_id=media_id,
        style="montage",
    )

    assert draft["timeline"] == "First_Pass_Timeline"
    assert draft["style"] == "montage"
    assert draft["cuts_count"] == 2
    assert len(draft["feedback_suggestions"]) > 0

    # Verify calls on harness mock session
    calls = [c[0] for c in mock_impl.calls]
    assert "ensure_timeline" in calls
    assert "place" in calls
    assert "set_clip_color" in calls

