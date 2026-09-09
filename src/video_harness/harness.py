from __future__ import annotations

from typing import Any

from video_harness.clip_colors import normalize_clip_color
from video_harness.mark import event_to_upsert, events_from_clip_metadata
from video_harness.registry import TypeRegistry
from video_harness.session import Session


class Harness:
    def __init__(self, session: Session, registry: TypeRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or TypeRegistry.load()

    def doctor_live(self) -> dict[str, Any]:
        ping = self.session.ping()
        inspect = self.session.call("inspect", {"media": "current", "item_markers": False})
        return {
            "transport": self.session.transport,
            "ping": ping,
            "project": (inspect.get("project") or {}).get("name"),
            "timeline": ((inspect.get("timeline") or {}).get("name")),
        }

    def inspect(self, media: str = "current") -> dict[str, Any]:
        result = self.session.call("inspect", {"media": media, "item_markers": True})
        result["transport"] = self.session.transport
        result["types"] = self.registry.to_dict()
        return result

    def import_media(self, paths: list[str]) -> dict[str, Any]:
        return self.session.call("import_media", {"paths": paths})

    def ensure_timeline(self, name: str | None = None) -> dict[str, Any]:
        return self.session.call("ensure_timeline", {"name": name} if name else {})

    def place(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return self.session.call("place", {"items": items})

    def lift(self, **params: Any) -> dict[str, Any]:
        return self.session.call("lift", params)

    def assemble(
        self,
        *,
        timeline: str,
        paths: list[str] | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        imported = None
        if paths:
            imported = self.import_media(paths)
        ensured = self.ensure_timeline(timeline)
        placements = items
        if not placements and imported:
            placements = [
                {"media_id": clip["media_id"], "track_type": "video", "track_index": 1}
                for clip in imported.get("imported") or []
            ]
        placed = self.place(placements) if placements else {"placed": [], "count": 0}
        return {"imported": imported, "timeline": ensured, "placed": placed}

    def set_clip_color(self, **params: Any) -> dict[str, Any]:
        color = params.get("color")
        if color:
            params = {**params, "color": normalize_clip_color(color)}
        return self.session.call("set_clip_color", params)

    def insert_title(self, **params: Any) -> dict[str, Any]:
        return self.session.call("insert_title", params)

    def insert_generator(self, **params: Any) -> dict[str, Any]:
        return self.session.call("insert_generator", params)

    def marker_upsert(self, markers: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
        if isinstance(markers, dict):
            markers = [markers]
        return self.session.call("marker_upsert", {"markers": markers})

    def markers_query(self, **params: Any) -> dict[str, Any]:
        return self.session.call("markers_query", params)

    def markers_clear(self, **params: Any) -> dict[str, Any]:
        return self.session.call("markers_clear", params)

    def markers_from_metadata(
        self,
        events: list[dict[str, Any]] | None = None,
        *,
        from_clips: bool = False,
        field_map: dict[str, str] | None = None,
        media: str = "all",
    ) -> dict[str, Any]:
        snapshot = self.inspect(media=media)
        timeline = snapshot.get("timeline") or {}
        clips = (snapshot.get("media") or {}).get("clips") or []
        incoming = list(events or [])
        if from_clips:
            incoming.extend(events_from_clip_metadata(clips, field_map=field_map))
        upserts = [
            event_to_upsert(event, self.registry, timeline=timeline, media_clips=clips)
            for event in incoming
        ]
        if not upserts:
            return {"markers": [], "count": 0, "events": 0}
        result = self.marker_upsert(upserts)
        result["events"] = len(incoming)
        return result

    def clip_metadata_get(self, **params: Any) -> dict[str, Any]:
        return self.session.call("clip_metadata_get", params)
