from video_harness.timecode import coerce_frame, frames_to_timecode, timecode_to_frames


def test_roundtrip_24fps():
    frame = timecode_to_frames("01:00:02:12", 24)
    assert frame == 86400 + 2 * 24 + 12
    assert frames_to_timecode(frame, 24) == "01:00:02:12"


def test_coerce_number_or_timecode():
    assert coerce_frame(100, 24) == 100
    assert coerce_frame("01:00:00:10", 24) == 86400 + 10
