from __future__ import annotations

import json
from typing import Any

from video_harness import __version__
from video_harness.errors import HarnessError
from video_harness.harness import Harness
from video_harness.registry import TypeRegistry
from video_harness.session import Session, connect

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP  # type: ignore


mcp = FastMCP("video-harness")
_session: Session | None = None
_harness: Harness | None = None


def _ok(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(exc: Exception) -> str:
    if isinstance(exc, HarnessError):
        return _ok({"error": exc.to_dict()})
    return _ok({"error": {"type": type(exc).__name__, "message": str(exc)}})


def get_harness() -> Harness:
    global _session, _harness
    if _harness is None:
        _session = connect()
        _harness = Harness(_session)
    return _harness


def reset_harness() -> None:
    global _session, _harness
    _session = None
    _harness = None


@mcp.tool()
def doctor() -> str:
    """Diagnose Resolve connection (direct Studio scripting vs free-edition in-app bridge)."""
    from video_harness.cli import cmd_doctor
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    try:
        live = get_harness().doctor_live()
    except Exception as exc:
        live = {"live": _err(exc)}
    with redirect_stdout(buf):
        cmd_doctor(None)  # type: ignore[arg-type]
    static = json.loads(buf.getvalue() or "{}")
    static["live"] = live
    return _ok(static)


@mcp.tool()
def reconnect() -> str:
    """Drop the cached Resolve session and connect again."""
    reset_harness()
    try:
        ping = get_harness().session.ping()
        return _ok({"reconnected": True, "ping": ping})
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def inspect(media: str = "current") -> str:
    """Snapshot of app, project, current timeline (tracks, items, markers), and media pool.

    media: 'current' (current bin) or 'all' (entire pool).
    """
    try:
        return _ok(get_harness().inspect(media=media))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def type_registry_get() -> str:
    """Marker type registry: id → color, scope (timeline|item|clip), duration (point|range)."""
    return _ok(TypeRegistry.load().to_dict())


@mcp.tool()
def media_import(paths: list[str]) -> str:
    """Import files into the current media pool folder. Returns media_id for each clip."""
    try:
        return _ok(get_harness().import_media(paths))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def timeline_ensure(name: str) -> str:
    """Create the named timeline if needed and switch to it. Idempotent."""
    try:
        return _ok(get_harness().ensure_timeline(name))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def timeline_place(items: list[dict[str, Any]]) -> str:
    """Place clips on the current timeline.

    Each item: media_id or clip_name or path; optional track_type, track_index,
    record_frame, source_in, source_out, media_type (1=video, 2=audio).
    """
    try:
        return _ok(get_harness().place(items))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def timeline_lift(
    unique_ids: list[str] | None = None,
    start: float | None = None,
    end: float | None = None,
    track_type: str | None = None,
    track_index: int | None = None,
    ripple: bool = False,
) -> str:
    """Delete timeline items by unique_id or by range. Effects on those items are lost."""
    params: dict[str, Any] = {"ripple": ripple}
    if unique_ids:
        params["unique_ids"] = unique_ids
    if start is not None:
        params["start"] = start
    if end is not None:
        params["end"] = end
    if track_type:
        params["track_type"] = track_type
    if track_index is not None:
        params["track_index"] = track_index
    try:
        return _ok(get_harness().lift(**params))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def timeline_assemble(
    timeline: str,
    paths: list[str] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> str:
    """Ensure a timeline, optionally import media, and place clips. Rough cut in one call."""
    try:
        return _ok(get_harness().assemble(timeline=timeline, paths=paths, items=items))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def clip_set_color(
    color: str,
    unique_ids: list[str] | None = None,
    media_id: str | None = None,
    clip_name: str | None = None,
) -> str:
    """Set Resolve clip color on timeline items (Orange, Green, Blue, …). Empty color clears.

    Match by unique_ids, media_id, or clip_name. If none given, colors every video/audio item.
    """
    params: dict[str, Any] = {"color": color}
    if unique_ids:
        params["unique_ids"] = unique_ids
    if media_id:
        params["media_id"] = media_id
    if clip_name:
        params["clip_name"] = clip_name
    try:
        return _ok(get_harness().set_clip_color(**params))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def marker_upsert(markers: list[dict[str, Any]]) -> str:
    """Create or replace typed markers. Idempotent on payload.id.

    Each marker: type/name, frame, optional scope (timeline|item|clip), color, note,
    duration, unique_id (item), media_id (clip), payload {id, type, source, attrs}.
    If payload is omitted, pass type and id and the server will still store customData JSON
    if you include payload. Prefer markers_from_metadata for mapping.
    """
    try:
        return _ok(get_harness().marker_upsert(markers))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def markers_query(
    type: str | None = None,
    color: str | None = None,
    scope: str | None = None,
    start: float | None = None,
    end: float | None = None,
) -> str:
    """Query timeline, item, and clip markers. Filter by type, color, scope, frame range."""
    params = {k: v for k, v in {
        "type": type, "color": color, "scope": scope, "start": start, "end": end
    }.items() if v is not None}
    try:
        return _ok(get_harness().markers_query(**params))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def markers_from_metadata(
    events: list[dict[str, Any]] | None = None,
    from_clips: bool = False,
    field_map: dict[str, str] | None = None,
) -> str:
    """Map metadata events onto typed markers.

    Event: {type, at (timecode or frame), id?, duration_frames?, note?, scope?,
    media_id? or clip: {media_id, name, path}, attrs?, source?}.
    from_clips=true also stamps clip metadata fields (Keywords, Shot, …) as clip-scope markers.
    """
    try:
        return _ok(
            get_harness().markers_from_metadata(
                events, from_clips=from_clips, field_map=field_map, media="all" if from_clips else "current"
            )
        )
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def markers_clear(
    scope: str = "timeline",
    id: str | None = None,
    color: str | None = None,
    frame: float | None = None,
    unique_id: str | None = None,
    media_id: str | None = None,
) -> str:
    """Delete markers by payload id, frame, or color. scope: timeline (default), item, clip."""
    params: dict[str, Any] = {"scope": scope}
    if id:
        params["id"] = id
    if color:
        params["color"] = color
    if frame is not None:
        params["frame"] = frame
    if unique_id:
        params["unique_id"] = unique_id
    if media_id:
        params["media_id"] = media_id
    try:
        return _ok(get_harness().markers_clear(**params))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def clip_metadata_get(media_id: str | None = None, clip_name: str | None = None, path: str | None = None) -> str:
    """Read built-in and third-party metadata for a media pool clip."""
    params = {k: v for k, v in {"media_id": media_id, "clip_name": clip_name, "path": path}.items() if v}
    try:
        return _ok(get_harness().clip_metadata_get(**params))
    except Exception as exc:
        return _err(exc)


@mcp.resource("resolve://status")
def resource_status() -> str:
    """Connection, product, version, page, project, timeline name."""
    try:
        return _ok(get_harness().doctor_live())
    except Exception as exc:
        return _err(exc)


@mcp.resource("resolve://timeline")
def resource_timeline() -> str:
    """Full current-timeline inspect including tracks, items, and markers."""
    try:
        snap = get_harness().inspect(media="current")
        return _ok(snap.get("timeline"))
    except Exception as exc:
        return _err(exc)


@mcp.resource("resolve://types")
def resource_types() -> str:
    """Marker type registry."""
    return _ok(TypeRegistry.load().to_dict())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
