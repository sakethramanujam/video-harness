from __future__ import annotations

import uuid
from typing import Any

from video_harness.errors import MarkerError, UnknownTypeError
from video_harness.paths import MARKER_SCHEMA
from video_harness.registry import TypeRegistry
from video_harness.timecode import coerce_frame, parse_fps


def build_payload(
    *,
    type_id: str,
    marker_id: str | None = None,
    source: str = "manual",
    attrs: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": MARKER_SCHEMA,
        "type": type_id,
        "id": marker_id or f"{type_id}-{uuid.uuid4().hex[:10]}",
        "source": source,
        "attrs": attrs or {},
    }
    if extra:
        payload.update(extra)
    return payload


def event_to_upsert(
    event: dict[str, Any],
    registry: TypeRegistry,
    *,
    timeline: dict[str, Any] | None = None,
    media_clips: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    type_id = event.get("type")
    if not type_id:
        raise MarkerError("event.type is required.")
    try:
        spec = registry.get(type_id)
    except UnknownTypeError:
        raise
    scope = event.get("scope") or spec.scope
    fps = parse_fps((timeline or {}).get("fps"), 24.0)
    at = event.get("at", event.get("frame"))
    if at is None:
        raise MarkerError("event.at or event.frame is required.", state={"event": event})

    clip = _resolve_clip(event, media_clips or [], timeline or {})
    if scope == "timeline":
        frame = coerce_frame(at, fps)
    elif scope == "item":
        if not clip:
            raise MarkerError(
                "item-scope markers need a clip that is on the timeline (media_id / unique_id / name).",
                state={"event": event},
            )
        source_frame = _source_frame(at, clip, fps)
        frame = source_frame - float(clip.get("source_start") or 0)
        if frame < 0:
            frame = 0
    else:
        clip_fps = parse_fps((clip or {}).get("fps"), fps)
        frame = coerce_frame(at, clip_fps)

    duration = event.get("duration_frames", event.get("duration"))
    if duration is None:
        duration = 1 if spec.duration == "point" else event.get("duration_frames") or 1

    payload = build_payload(
        type_id=type_id,
        marker_id=event.get("id"),
        source=event.get("source") or "sidecar",
        attrs=event.get("attrs") or {},
        extra={k: event[k] for k in ("clip_media_id", "confidence") if k in event},
    )
    if clip and clip.get("media_id"):
        payload.setdefault("clip_media_id", clip["media_id"])

    upsert: dict[str, Any] = {
        "scope": scope,
        "frame": frame,
        "color": event.get("color") or spec.color,
        "name": event.get("name") or type_id.replace(" ", "-"),
        "note": event.get("note") or "",
        "duration": duration,
        "payload": payload,
    }
    if scope == "item" and clip:
        upsert["unique_id"] = clip.get("unique_id")
    if scope == "clip":
        if clip and clip.get("media_id"):
            upsert["media_id"] = clip["media_id"]
        elif event.get("media_id") or (event.get("clip") or {}).get("media_id"):
            upsert["media_id"] = event.get("media_id") or (event.get("clip") or {}).get("media_id")
        if clip and clip.get("name"):
            upsert["clip_name"] = clip["name"]
        elif event.get("clip_name"):
            upsert["clip_name"] = event["clip_name"]
        path = (clip or {}).get("path") or event.get("path") or (event.get("clip") or {}).get("path")
        if path:
            upsert["path"] = path
    return upsert


def _source_frame(at: Any, clip: dict[str, Any], timeline_fps: float) -> float:
    fps = parse_fps(clip.get("fps"), timeline_fps)
    return coerce_frame(at, fps)


def _resolve_clip(
    event: dict[str, Any],
    media_clips: list[dict[str, Any]],
    timeline: dict[str, Any],
) -> dict[str, Any] | None:
    media_id = event.get("media_id") or (event.get("clip") or {}).get("media_id")
    unique_id = event.get("unique_id") or (event.get("clip") or {}).get("unique_id")
    name = event.get("clip_name") or (event.get("clip") or {}).get("name")
    path = event.get("path") or (event.get("clip") or {}).get("path")
    for track in timeline.get("tracks") or []:
        for item in track.get("items") or []:
            if unique_id and item.get("unique_id") == unique_id:
                return item
            if media_id and item.get("media_id") == media_id:
                return item
            if name and item.get("name") == name:
                return item
            if path and item.get("path") == path:
                return item
    for clip in media_clips:
        if media_id and clip.get("media_id") == media_id:
            return clip
        if unique_id and clip.get("unique_id") == unique_id:
            return clip
        if name and clip.get("name") == name:
            return clip
        if path and clip.get("path") == path:
            return clip
    return None


def events_from_clip_metadata(
    clips: list[dict[str, Any]],
    *,
    field_map: dict[str, str] | None = None,
    source: str = "clip-metadata",
) -> list[dict[str, Any]]:
    """Turn clip metadata fields into marker events.

    field_map keys are metadata field names, values are marker type ids.
    Default: Keywords -> keyword, Comments -> keyword, Shot -> chapter.
    """
    mapping = field_map or {
        "Keywords": "keyword",
        "Comments": "keyword",
        "Shot": "chapter",
        "Scene": "chapter",
        "Good Take": "keyword",
    }
    events: list[dict[str, Any]] = []
    for clip in clips:
        metadata = dict(clip.get("metadata") or {})
        metadata.update(clip.get("third_party") or {})
        for field, type_id in mapping.items():
            value = metadata.get(field)
            if value in (None, "", [], {}):
                continue
            text = value if isinstance(value, str) else str(value)
            events.append(
                {
                    "type": type_id,
                    "id": f"{type_id}-{clip.get('media_id') or clip.get('name')}-{field}",
                    "at": 0,
                    "scope": "clip",
                    "note": f"{field}: {text}",
                    "source": source,
                    "media_id": clip.get("media_id"),
                    "attrs": {"field": field, "value": text},
                }
            )
    return events
