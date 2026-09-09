import pytest
from video_harness.vision.spatio_temporal import (
    analyze_spatial_frame,
    SpatioTemporalSceneAnalyzer,
    FrameVisualMetrics,
)


def test_analyze_spatial_frame_uniform_vs_detailed():
    width = 100
    height = 100

    # 1. Uniform flat black frame (uncomposed / dead)
    flat_frame = bytes([10] * (width * height * 3))
    metrics_flat = analyze_spatial_frame(flat_frame, width, height)
    assert metrics_flat.edge_energy == 0.0
    assert metrics_flat.contrast_std == 0.0
    assert metrics_flat.visual_clarity_score < 4.0

    # 2. High contrast, textured frame
    textured = bytearray(width * height * 3)
    for y in range(height):
        for x in range(width):
            idx = (y * width + x) * 3
            val = 220 if ((x // 10) % 2 == (y // 10) % 2) else 30
            textured[idx] = val
            textured[idx + 1] = val
            textured[idx + 2] = val

    metrics_text = analyze_spatial_frame(bytes(textured), width, height)
    assert metrics_text.edge_energy > 5.0
    assert metrics_text.contrast_std > 30.0
    assert metrics_text.visual_clarity_score > 6.0


def test_spatio_temporal_analyzer_motion_and_classification():
    analyzer = SpatioTemporalSceneAnalyzer(quality_threshold=4.5)
    width = 60
    height = 60

    frame1 = bytearray(width * height * 3)
    for i in range(0, len(frame1), 3):
        frame1[i] = 150
        frame1[i + 1] = 120
        frame1[i + 2] = 90

    # Frame 1: Initial state
    analyzer.process_frame(bytes(frame1), width, height, pts_sec=0.0, source_frame=0)

    # Frame 2: Smooth motion (slight shift in values)
    frame2 = bytearray(frame1)
    for i in range(0, len(frame2), 3):
        frame2[i] = min(255, frame2[i] + 10)
    analyzer.process_frame(bytes(frame2), width, height, pts_sec=1.0, source_frame=24)

    # Frame 3: Another smooth progression
    frame3 = bytearray(frame2)
    for i in range(0, len(frame3), 3):
        frame3[i] = min(255, frame3[i] + 10)
    analyzer.process_frame(bytes(frame3), width, height, pts_sec=2.0, source_frame=48)

    scene = analyzer.synthesize_scene(
        start_frame=0,
        end_frame=48,
        start_pts=0.0,
        end_pts=2.0,
        camera_metadata={"movement_profile": "smooth_tracking", "avg_alt_m": 45.0},
    )

    assert scene.duration_sec == 2.0
    assert scene.dynamics in ("smooth_tracking", "locked_static")
    assert "visual quality" in scene.summary
    assert "alt 45.0m" in scene.summary
