from video_harness.errors import UnknownTypeError
from video_harness.registry import TypeRegistry


def test_default_registry_has_core_types():
    registry = TypeRegistry.load()
    beat = registry.get("beat")
    assert beat.color == "Cyan"
    assert beat.scope == "timeline"
    dialogue = registry.get("dialogue")
    assert dialogue.scope == "item"
    assert dialogue.duration == "range"


def test_unknown_type():
    registry = TypeRegistry.load()
    try:
        registry.get("not-a-type")
        raise AssertionError("expected UnknownTypeError")
    except UnknownTypeError as exc:
        assert "not-a-type" in exc.message
