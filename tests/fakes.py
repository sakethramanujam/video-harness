from __future__ import annotations

from typing import Any


class FakeFolder:
    def __init__(self, name: str = "Master") -> None:
        self._name = name
        self.clips: list[FakeMedia] = []
        self.subs: list[FakeFolder] = []

    def GetName(self) -> str:
        return self._name

    def GetClipList(self) -> list[FakeMedia]:
        return list(self.clips)

    def GetSubFolderList(self) -> list[FakeFolder]:
        return list(self.subs)

    def GetUniqueId(self) -> str:
        return f"folder-{self._name}"


class FakeMedia:
    def __init__(self, name: str, media_id: str, path: str = "", frames: int = 100) -> None:
        self._name = name
        self._media_id = media_id
        self._uid = f"uid-{media_id}"
        self._path = path
        self._frames = frames
        self.metadata: dict[str, str] = {}
        self.third: dict[str, str] = {}
        self.markers: dict[float, dict[str, Any]] = {}
        self.color = ""

    def GetName(self) -> str:
        return self._name

    def GetMediaId(self) -> str:
        return self._media_id

    def GetUniqueId(self) -> str:
        return self._uid

    def GetClipProperty(self) -> dict[str, Any]:
        return {"File Path": self._path, "FPS": "24", "Frames": str(self._frames)}

    def GetMetadata(self) -> dict[str, str]:
        return dict(self.metadata)

    def GetThirdPartyMetadata(self) -> dict[str, str]:
        return dict(self.third)

    def SetMetadata(self, metadata: dict[str, str]) -> bool:
        self.metadata.update(metadata)
        return True

    def SetThirdPartyMetadata(self, metadata: dict[str, str]) -> bool:
        self.third.update(metadata)
        return True

    def GetClipColor(self) -> str:
        return self.color

    def GetFlagList(self) -> list[str]:
        return []

    def GetMarkers(self) -> dict[float, dict[str, Any]]:
        return dict(self.markers)

    def AddMarker(self, frame, color, name, note, duration, customData="") -> bool:
        self.markers[float(frame)] = {
            "color": color,
            "name": name,
            "note": note,
            "duration": duration,
            "customData": customData,
        }
        return True

    def DeleteMarkerAtFrame(self, frame) -> bool:
        return self.markers.pop(float(frame), None) is not None

    def DeleteMarkersByColor(self, color: str) -> bool:
        if color == "All":
            self.markers.clear()
            return True
        self.markers = {k: v for k, v in self.markers.items() if v.get("color") != color}
        return True


class FakeItem:
    def __init__(self, media: FakeMedia, start: int, duration: int, source_start: int = 0) -> None:
        self.media = media
        self._start = start
        self._duration = duration
        self._source_start = source_start
        self._uid = f"item-{media._media_id}-{start}"
        self.markers: dict[float, dict[str, Any]] = {}
        self.color = ""

    def GetName(self) -> str:
        return self.media.GetName()

    def GetUniqueId(self) -> str:
        return self._uid

    def GetStart(self) -> int:
        return self._start

    def GetEnd(self) -> int:
        return self._start + self._duration

    def GetDuration(self) -> int:
        return self._duration

    def GetSourceStartFrame(self) -> int:
        return self._source_start

    def GetSourceEndFrame(self) -> int:
        return self._source_start + self._duration

    def GetClipColor(self) -> str:
        return self.color

    def SetClipColor(self, color: str) -> bool:
        from video_harness.clip_colors import CLIP_COLORS

        if color not in CLIP_COLORS:
            return False
        self.color = color
        return True

    def ClearClipColor(self) -> bool:
        self.color = ""
        return True

    def GetMediaPoolItem(self) -> FakeMedia:
        return self.media

    def GetMarkers(self) -> dict[float, dict[str, Any]]:
        return dict(self.markers)

    def AddMarker(self, frame, color, name, note, duration, customData="") -> bool:
        self.markers[float(frame)] = {
            "color": color,
            "name": name,
            "note": note,
            "duration": duration,
            "customData": customData,
        }
        return True

    def DeleteMarkerAtFrame(self, frame) -> bool:
        return self.markers.pop(float(frame), None) is not None

    def DeleteMarkersByColor(self, color: str) -> bool:
        if color == "All":
            self.markers.clear()
            return True
        self.markers = {k: v for k, v in self.markers.items() if v.get("color") != color}
        return True


class FakeTimeline:
    def __init__(self, name: str = "Edit") -> None:
        self._name = name
        self._uid = f"tl-{name}"
        self.start = 86400
        self.video: list[list[FakeItem]] = [[]]
        self.audio: list[list[FakeItem]] = [[]]
        self.subtitle: list[list[FakeItem]] = [[]]
        self.markers: dict[float, dict[str, Any]] = {}
        self.current_tc = "01:00:00:00"

    def GetName(self) -> str:
        return self._name

    def GetUniqueId(self) -> str:
        return self._uid

    def GetStartFrame(self) -> int:
        return self.start

    def GetEndFrame(self) -> int:
        last = self.start
        for items in self.video:
            for item in items:
                last = max(last, item.GetEnd())
        return last

    def GetStartTimecode(self) -> str:
        return "01:00:00:00"

    def GetCurrentTimecode(self) -> str:
        return self.current_tc

    def GetSetting(self, key: str) -> str:
        return {"timelineFrameRate": "24"}.get(key, "")

    def GetTrackCount(self, track_type: str) -> int:
        return len(getattr(self, track_type))

    def GetTrackName(self, track_type: str, index: int) -> str:
        prefix = {"video": "V", "audio": "A", "subtitle": "S"}[track_type]
        return f"{prefix}{index}"

    def GetIsTrackEnabled(self, track_type: str, index: int) -> bool:
        return True

    def GetIsTrackLocked(self, track_type: str, index: int) -> bool:
        return False

    def GetItemListInTrack(self, track_type: str, index: int) -> list[FakeItem]:
        tracks = getattr(self, track_type)
        return list(tracks[index - 1])

    def AddTrack(self, track_type: str) -> bool:
        getattr(self, track_type).append([])
        return True

    def DeleteClips(self, items: list[FakeItem], ripple: bool = False) -> bool:
        victim = set(id(i) for i in items)
        for track_type in ("video", "audio", "subtitle"):
            tracks = getattr(self, track_type)
            for i, row in enumerate(tracks):
                tracks[i] = [it for it in row if id(it) not in victim]
        return True

    def GetMarkers(self) -> dict[float, dict[str, Any]]:
        return dict(self.markers)

    def AddMarker(self, frame, color, name, note, duration, customData="") -> bool:
        self.markers[float(frame)] = {
            "color": color,
            "name": name,
            "note": note,
            "duration": duration,
            "customData": customData,
        }
        return True

    def DeleteMarkerAtFrame(self, frame) -> bool:
        return self.markers.pop(float(frame), None) is not None

    def DeleteMarkersByColor(self, color: str) -> bool:
        if color == "All":
            self.markers.clear()
            return True
        self.markers = {k: v for k, v in self.markers.items() if v.get("color") != color}
        return True


class FakePool:
    def __init__(self, root: FakeFolder, timeline: FakeTimeline) -> None:
        self.root = root
        self.current = root
        self.timeline = timeline
        self.timelines: dict[str, FakeTimeline] = {timeline.GetName(): timeline}

    def GetRootFolder(self) -> FakeFolder:
        return self.root

    def GetCurrentFolder(self) -> FakeFolder:
        return self.current

    def ImportMedia(self, paths: list[str]) -> list[FakeMedia]:
        imported = []
        for path in paths:
            name = path.rsplit("/", 1)[-1]
            media = FakeMedia(name, media_id=f"id-{name}", path=path)
            self.root.clips.append(media)
            imported.append(media)
        return imported

    def CreateEmptyTimeline(self, name: str) -> FakeTimeline:
        tl = FakeTimeline(name)
        self.timelines[name] = tl
        self.timeline = tl
        return tl

    def AppendToTimeline(self, clip_infos: list[dict[str, Any]]) -> list[FakeItem]:
        placed = []
        for info in clip_infos:
            media: FakeMedia = info["mediaPoolItem"]
            track_index = int(info.get("trackIndex") or 1)
            while len(self.timeline.video) < track_index:
                self.timeline.AddTrack("video")
            start = int(info.get("recordFrame") if info.get("recordFrame") is not None else self.timeline.GetEndFrame())
            src_in = int(info.get("startFrame") or 0)
            src_out = int(info.get("endFrame") or (src_in + 24))
            duration = max(1, src_out - src_in)
            item = FakeItem(media, start, duration, source_start=src_in)
            self.timeline.video[track_index - 1].append(item)
            placed.append(item)
        return placed


class FakeProject:
    def __init__(self, pool: FakePool, timeline: FakeTimeline) -> None:
        self._name = "Show"
        self.pool = pool
        self.current = timeline

    def GetName(self) -> str:
        return self._name

    def GetTimelineCount(self) -> int:
        return len(self.pool.timelines)

    def GetTimelineByIndex(self, index: int) -> FakeTimeline:
        return list(self.pool.timelines.values())[index - 1]

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.current

    def SetCurrentTimeline(self, tl: FakeTimeline) -> bool:
        self.current = tl
        self.pool.timeline = tl
        return True

    def GetMediaPool(self) -> FakePool:
        return self.pool

    def GetSetting(self, key: str) -> str:
        return {
            "timelineFrameRate": "24",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }.get(key, "")


class FakePM:
    def __init__(self, project: FakeProject) -> None:
        self.project = project

    def GetCurrentProject(self) -> FakeProject:
        return self.project


class FakeResolve:
    def __init__(self) -> None:
        self.product = "DaVinci Resolve"
        self.version = "19.0.0"
        self.page = "edit"
        root = FakeFolder()
        clip = FakeMedia("A001.mov", "media-a001", path="/tmp/A001.mov", frames=240)
        clip.metadata["Keywords"] = "hero,wide"
        root.clips.append(clip)
        tl = FakeTimeline("Edit")
        pool = FakePool(root, tl)
        project = FakeProject(pool, tl)
        self.pm = FakePM(project)
        item = FakeItem(clip, 86400, 48, source_start=12)
        tl.video[0].append(item)

    def GetProductName(self) -> str:
        return self.product

    def GetVersionString(self) -> str:
        return self.version

    def GetCurrentPage(self) -> str:
        return self.page

    def GetProjectManager(self) -> FakePM:
        return self.pm
