"""Stdlib-only Resolve operations. Runs inside Resolve (bridge) or via fusionscript."""

import json
import traceback

MARKER_SCHEMA = "video-harness.marker/v1"
VALID_TRACKS = ("video", "audio", "subtitle")
CLIP_COLORS = (
    "Orange",
    "Apricot",
    "Yellow",
    "Lime",
    "Olive",
    "Green",
    "Teal",
    "Navy",
    "Blue",
    "Purple",
    "Violet",
    "Pink",
    "Tan",
    "Beige",
    "Brown",
    "Chocolate",
)
CLIP_COLOR_ALIASES = {
    "Cyan": "Teal",
    "Mint": "Lime",
    "Red": "Violet",
    "Crimson": "Violet",
    "Sky": "Navy",
    "Fuchsia": "Pink",
    "Magenta": "Pink",
    "Lemon": "Yellow",
    "Lavender": "Purple",
    "Rose": "Pink",
    "Sand": "Tan",
    "Cocoa": "Chocolate",
    "Cream": "Beige",
    "White": "Beige",
}


class Fail(Exception):
    def __init__(self, message, type="HarnessError", cause=None, fix=None, state=None):
        Exception.__init__(self, message)
        self.type = type
        self.message = message
        self.cause = cause
        self.fix = fix
        self.state = state or {}

    def to_dict(self):
        out = {"type": self.type, "message": self.message, "state": self.state}
        if self.cause:
            out["cause"] = self.cause
        if self.fix:
            out["fix"] = self.fix
        return out


def safe(fn, default=None):
    try:
        value = fn()
        if value is None:
            return default
        return value
    except Exception:
        return default


def _normalize_clip_color(color):
    if color is None:
        return ""
    text = str(color).strip()
    if text == "":
        return ""
    key = text.lower()
    for name in CLIP_COLORS:
        if name.lower() == key:
            return name
    for src, dst in CLIP_COLOR_ALIASES.items():
        if src.lower() == key:
            return dst
    raise Fail(
        "Invalid clip color '%s'. Valid: %s. Aliases: Cyan→Teal, Mint→Lime, Red→Violet."
        % (color, ", ".join(CLIP_COLORS)),
        type="PlacementError",
        state={"color": color, "valid": list(CLIP_COLORS)},
    )


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _project(resolve):
    pm = safe(lambda: resolve.GetProjectManager())
    if not pm:
        raise Fail("No project manager.", type="ConnectionError", fix="Is Resolve running?")
    proj = safe(lambda: pm.GetCurrentProject())
    if not proj:
        raise Fail(
            "No project is open.",
            type="NoProjectError",
            fix="Open a project in DaVinci Resolve, then retry.",
        )
    return pm, proj


def _timeline(resolve):
    pm, proj = _project(resolve)
    tl = safe(lambda: proj.GetCurrentTimeline())
    if not tl:
        raise Fail(
            "No timeline is current.",
            type="NoTimelineError",
            fix="Create or switch to a timeline first.",
        )
    return pm, proj, tl


def _pool(resolve):
    _, proj = _project(resolve)
    pool = safe(lambda: proj.GetMediaPool())
    if not pool:
        raise Fail("No media pool.", type="NoProjectError")
    return proj, pool


def _iter_folders(folder):
    yield folder
    for sub in safe(lambda: folder.GetSubFolderList(), []) or []:
        for item in _iter_folders(sub):
            yield item


def _clip_list(folder):
    return list(safe(lambda: folder.GetClipList(), []) or [])


def _clip_path(clip):
    props = safe(lambda: clip.GetClipProperty()) or {}
    return props.get("File Path") or props.get("File Path") or ""


def find_clip(pool, params):
    media_id = params.get("media_id") or params.get("mediaId")
    unique_id = params.get("unique_id") or params.get("uniqueId")
    name = params.get("clip_name") or params.get("clipName")
    path = params.get("path") or params.get("filePath")
    root = pool.GetRootFolder()
    if not root:
        return None
    for folder in _iter_folders(root):
        for clip in _clip_list(folder):
            if media_id and safe(lambda c=clip: c.GetMediaId()) == media_id:
                return clip
            if unique_id and safe(lambda c=clip: c.GetUniqueId()) == unique_id:
                return clip
            if path:
                clip_path = _clip_path(clip)
                if clip_path and clip_path == path:
                    return clip
            if name and safe(lambda c=clip: c.GetName()) == name:
                return clip
    return None


def serialize_markers(raw):
    out = []
    if not raw:
        return out
    items = raw.items() if hasattr(raw, "items") else []
    for frame, info in items:
        row = dict(info or {})
        row["frame"] = float(frame)
        custom = row.get("customData") or ""
        parsed = _parse_custom(custom)
        if parsed:
            row["payload"] = parsed
        out.append(json_safe(row))
    out.sort(key=lambda m: m.get("frame", 0))
    return out


def _parse_custom(custom):
    if not custom:
        return None
    try:
        data = json.loads(custom)
    except Exception:
        return None
    if isinstance(data, dict):
        return data
    return None


def encode_payload(payload):
    body = dict(payload or {})
    body.setdefault("schema", MARKER_SCHEMA)
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def _payload_id(custom):
    parsed = _parse_custom(custom) if isinstance(custom, str) else custom
    if isinstance(parsed, dict):
        return parsed.get("id")
    return None


def ping(resolve, params=None):
    return {
        "ok": True,
        "product": safe(lambda: resolve.GetProductName()),
        "version": safe(lambda: resolve.GetVersionString()),
        "page": safe(lambda: resolve.GetCurrentPage()),
        "methods": list(METHODS.keys()),
    }


def inspect(resolve, params=None):
    params = params or {}
    result = {
        "app": ping(resolve),
        "project": None,
        "timeline": None,
        "media": None,
    }
    pm = safe(lambda: resolve.GetProjectManager())
    proj = safe(lambda: pm.GetCurrentProject()) if pm else None
    if not proj:
        return result
    result["project"] = {
        "name": safe(lambda: proj.GetName()),
        "timeline_count": safe(lambda: proj.GetTimelineCount(), 0),
        "fps": safe(lambda: proj.GetSetting("timelineFrameRate")),
        "width": safe(lambda: proj.GetSetting("timelineResolutionWidth")),
        "height": safe(lambda: proj.GetSetting("timelineResolutionHeight")),
        "timelines": _list_timelines(proj),
    }
    tl = safe(lambda: proj.GetCurrentTimeline())
    if tl:
        result["timeline"] = _inspect_timeline(tl, include_item_markers=params.get("item_markers", True))
    media_mode = params.get("media", "current")
    if media_mode in ("none", False, None):
        pool = safe(lambda: proj.GetMediaPool())
        current = safe(lambda: pool.GetCurrentFolder()) if pool else None
        result["media"] = {
            "current_folder": safe(lambda: current.GetName()) if current else None,
            "clip_count": 0,
            "clips": [],
        }
    else:
        result["media"] = _inspect_media(proj, recurse=media_mode == "all")
    return result


def _list_timelines(proj):
    out = []
    count = int(safe(lambda: proj.GetTimelineCount(), 0) or 0)
    for index in range(1, count + 1):
        tl = safe(lambda i=index: proj.GetTimelineByIndex(i))
        if not tl:
            continue
        out.append(
            {
                "index": index,
                "name": safe(lambda t=tl: t.GetName()),
                "unique_id": safe(lambda t=tl: t.GetUniqueId()),
            }
        )
    return out


def _inspect_timeline(tl, include_item_markers=True):
    tracks = []
    for track_type in VALID_TRACKS:
        count = int(safe(lambda t=track_type: tl.GetTrackCount(t), 0) or 0)
        for index in range(1, count + 1):
            items_out = []
            items = safe(lambda t=track_type, i=index: tl.GetItemListInTrack(t, i), []) or []
            for item in items:
                mp = safe(lambda it=item: it.GetMediaPoolItem())
                row = {
                    "name": safe(lambda it=item: it.GetName()),
                    "unique_id": safe(lambda it=item: it.GetUniqueId()),
                    "start": safe(lambda it=item: it.GetStart()),
                    "end": safe(lambda it=item: it.GetEnd()),
                    "duration": safe(lambda it=item: it.GetDuration()),
                    "source_start": safe(lambda it=item: it.GetSourceStartFrame()),
                    "source_end": safe(lambda it=item: it.GetSourceEndFrame()),
                    "color": safe(lambda it=item: it.GetClipColor()) or "",
                    "media_id": safe(lambda m=mp: m.GetMediaId()) if mp else None,
                    "media_name": safe(lambda m=mp: m.GetName()) if mp else None,
                    "path": _clip_path(mp) if mp else "",
                }
                if include_item_markers:
                    row["markers"] = serialize_markers(safe(lambda it=item: it.GetMarkers(), {}))
                items_out.append(row)
            tracks.append(
                {
                    "type": track_type,
                    "index": index,
                    "name": safe(lambda t=track_type, i=index: tl.GetTrackName(t, i)),
                    "enabled": safe(lambda t=track_type, i=index: tl.GetIsTrackEnabled(t, i), True),
                    "locked": safe(lambda t=track_type, i=index: tl.GetIsTrackLocked(t, i), False),
                    "items": items_out,
                }
            )
    fps = safe(lambda: tl.GetSetting("timelineFrameRate"))
    return {
        "name": safe(lambda: tl.GetName()),
        "unique_id": safe(lambda: tl.GetUniqueId()),
        "start_frame": safe(lambda: tl.GetStartFrame()),
        "end_frame": safe(lambda: tl.GetEndFrame()),
        "start_timecode": safe(lambda: tl.GetStartTimecode()),
        "current_timecode": safe(lambda: tl.GetCurrentTimecode()),
        "fps": fps,
        "markers": serialize_markers(safe(lambda: tl.GetMarkers(), {})),
        "tracks": tracks,
    }


def _inspect_clip(clip, include_metadata=True):
    props = safe(lambda: clip.GetClipProperty()) or {}
    row = {
        "name": safe(lambda: clip.GetName()),
        "media_id": safe(lambda: clip.GetMediaId()),
        "unique_id": safe(lambda: clip.GetUniqueId()),
        "path": props.get("File Path") or "",
        "fps": props.get("FPS"),
        "frames": props.get("Frames"),
        "duration": props.get("Duration"),
        "resolution": props.get("Resolution"),
        "start_tc": props.get("Start TC"),
        "color": safe(lambda: clip.GetClipColor()) or "",
        "flags": safe(lambda: clip.GetFlagList(), []) or [],
        "markers": serialize_markers(safe(lambda: clip.GetMarkers(), {})),
    }
    if include_metadata:
        row["metadata"] = json_safe(safe(lambda: clip.GetMetadata(), {}) or {})
        row["third_party"] = json_safe(safe(lambda: clip.GetThirdPartyMetadata(), {}) or {})
    return row


def _inspect_media(proj, recurse=False):
    pool = safe(lambda: proj.GetMediaPool())
    if not pool:
        return None
    current = safe(lambda: pool.GetCurrentFolder())
    root = safe(lambda: pool.GetRootFolder())
    folder = root if recurse else current or root
    clips = []
    if recurse and root:
        for node in _iter_folders(root):
            for clip in _clip_list(node):
                clips.append(_inspect_clip(clip))
    else:
        for clip in _clip_list(folder) if folder else []:
            clips.append(_inspect_clip(clip))
    return {
        "current_folder": safe(lambda: current.GetName()) if current else None,
        "clip_count": len(clips),
        "clips": clips,
    }


def import_media(resolve, params=None):
    params = params or {}
    paths = params.get("paths") or params.get("filePaths") or []
    if not paths:
        raise Fail("paths is required.", type="PlacementError")
    _, pool = _pool(resolve)
    items = pool.ImportMedia(list(paths))
    if not items:
        raise Fail(
            "ImportMedia returned nothing.",
            type="PlacementError",
            cause="Resolve rejected the file list.",
            fix="Check the paths exist and are readable by Resolve.",
            state={"paths": list(paths)},
        )
    return {
        "imported": [_inspect_clip(item, include_metadata=False) for item in items],
        "count": len(items),
    }


def ensure_timeline(resolve, params=None):
    params = params or {}
    name = params.get("name")
    _, proj = _project(resolve)
    if name:
        count = int(safe(lambda: proj.GetTimelineCount(), 0) or 0)
        for index in range(1, count + 1):
            tl = safe(lambda i=index: proj.GetTimelineByIndex(i))
            if tl and safe(lambda t=tl: t.GetName()) == name:
                proj.SetCurrentTimeline(tl)
                return {"name": name, "created": False, "switched": True}
        pool = proj.GetMediaPool()
        tl = pool.CreateEmptyTimeline(name) if pool else None
        if not tl:
            raise Fail("Failed to create timeline '%s'." % name, type="PlacementError")
        proj.SetCurrentTimeline(tl)
        return {"name": name, "created": True, "switched": True}
    _, _, tl = _timeline(resolve)
    return {"name": safe(lambda: tl.GetName()), "created": False, "switched": False}


def _ensure_track(tl, track_type, index):
    track_type = track_type or "video"
    index = int(index or 1)
    if track_type not in VALID_TRACKS:
        raise Fail("Invalid track type '%s'." % track_type, type="PlacementError")
    count = int(safe(lambda: tl.GetTrackCount(track_type), 0) or 0)
    while count < index:
        ok = tl.AddTrack(track_type)
        if not ok:
            raise Fail(
                "Could not add %s track (have %s, need %s)." % (track_type, count, index),
                type="PlacementError",
            )
        count = int(safe(lambda: tl.GetTrackCount(track_type), 0) or 0)
    return index


def place(resolve, params=None):
    params = params or {}
    items = params.get("items") or []
    if not items:
        raise Fail("items is required.", type="PlacementError")
    _, proj, tl = _timeline(resolve)
    pool = proj.GetMediaPool()
    clip_infos = []
    missing = []
    for spec in items:
        lookup = dict(spec)
        if lookup.get("name") and not lookup.get("clip_name") and not lookup.get("media_id"):
            lookup["clip_name"] = lookup.get("name")
        clip = find_clip(pool, lookup)
        if not clip:
            missing.append(spec)
            continue
        track_type = spec.get("track_type") or spec.get("trackType") or "video"
        track_index = _ensure_track(tl, track_type, spec.get("track_index") or spec.get("trackIndex") or 1)
        info = {"mediaPoolItem": clip, "trackIndex": int(track_index)}
        if spec.get("record_frame") is not None or spec.get("recordFrame") is not None:
            info["recordFrame"] = spec.get("record_frame", spec.get("recordFrame"))
        if spec.get("source_in") is not None or spec.get("startFrame") is not None:
            info["startFrame"] = spec.get("source_in", spec.get("startFrame"))
        if spec.get("source_out") is not None or spec.get("endFrame") is not None:
            info["endFrame"] = spec.get("source_out", spec.get("endFrame"))
        media_type = spec.get("media_type", spec.get("mediaType"))
        if media_type is not None:
            info["mediaType"] = int(media_type)
        clip_infos.append(info)
    if missing:
        raise Fail(
            "Could not find %s clip(s) in the media pool." % len(missing),
            type="PlacementError",
            state={"missing": json_safe(missing)},
            fix="Import the media first, or pass media_id / path / name that exists in the pool.",
        )
    placed = pool.AppendToTimeline(clip_infos)
    if not placed:
        raise Fail(
            "AppendToTimeline returned nothing.",
            type="PlacementError",
            cause="Resolve rejected the clipInfo list.",
            fix="Check track_index, record_frame, and source in/out.",
        )
    out = []
    for item in placed:
        out.append(
            {
                "name": safe(lambda it=item: it.GetName()),
                "unique_id": safe(lambda it=item: it.GetUniqueId()),
                "start": safe(lambda it=item: it.GetStart()),
                "end": safe(lambda it=item: it.GetEnd()),
            }
        )
    return {"placed": out, "count": len(out)}


def lift(resolve, params=None):
    params = params or {}
    unique_ids = set(params.get("unique_ids") or params.get("uniqueIds") or [])
    ripple = bool(params.get("ripple", False))
    _, _, tl = _timeline(resolve)
    targets = []
    for track_type in VALID_TRACKS:
        count = int(safe(lambda t=track_type: tl.GetTrackCount(t), 0) or 0)
        for index in range(1, count + 1):
            items = safe(lambda t=track_type, i=index: tl.GetItemListInTrack(t, i), []) or []
            for item in items:
                uid = safe(lambda it=item: it.GetUniqueId())
                if unique_ids and uid in unique_ids:
                    targets.append(item)
                    continue
                if not unique_ids:
                    start = params.get("start")
                    end = params.get("end")
                    track_filter = params.get("track_type") or params.get("trackType")
                    index_filter = params.get("track_index") or params.get("trackIndex")
                    if track_filter and track_filter != track_type:
                        continue
                    if index_filter is not None and int(index_filter) != index:
                        continue
                    if start is None and end is None:
                        continue
                    item_start = safe(lambda it=item: it.GetStart(), 0)
                    item_end = safe(lambda it=item: it.GetEnd(), 0)
                    if start is not None and item_end <= start:
                        continue
                    if end is not None and item_start >= end:
                        continue
                    targets.append(item)
    if not targets:
        raise Fail("No matching timeline items to lift.", type="PlacementError")
    ok = tl.DeleteClips(targets, ripple)
    return {"success": bool(ok), "deleted": len(targets), "ripple": ripple}


def _marker_host(resolve, params):
    scope = params.get("scope") or "timeline"
    _, proj, tl = _timeline(resolve)
    if scope == "timeline":
        return tl, "timeline"
    if scope == "item":
        uid = params.get("unique_id") or params.get("uniqueId")
        if not uid:
            raise Fail("unique_id is required for item-scope markers.", type="MarkerError")
        for track_type in VALID_TRACKS:
            count = int(safe(lambda t=track_type: tl.GetTrackCount(t), 0) or 0)
            for index in range(1, count + 1):
                items = safe(lambda t=track_type, i=index: tl.GetItemListInTrack(t, i), []) or []
                for item in items:
                    if safe(lambda it=item: it.GetUniqueId()) == uid:
                        return item, "item"
        raise Fail("Timeline item '%s' not found." % uid, type="MarkerError")
    if scope == "clip":
        pool = proj.GetMediaPool()
        clip = find_clip(pool, params)
        if not clip:
            raise Fail("Media pool clip not found.", type="MarkerError", state={"params": json_safe(params)})
        return clip, "clip"
    raise Fail("Unknown marker scope '%s'." % scope, type="MarkerError")


def marker_upsert(resolve, params=None):
    params = params or {}
    markers = params.get("markers")
    if markers is None:
        markers = [params]
    results = []
    for spec in markers:
        results.append(_upsert_one(resolve, spec))
    return {"markers": results, "count": len(results)}


def _upsert_one(resolve, spec):
    host, scope = _marker_host(resolve, spec)
    frame = spec.get("frame")
    if frame is None:
        raise Fail("frame is required.", type="MarkerError")
    frame = float(frame)
    color = spec.get("color") or "Blue"
    name = spec.get("name") or spec.get("type") or "mark"
    note = spec.get("note") or ""
    duration = spec.get("duration", 1)
    payload = spec.get("payload")
    if payload is None and spec.get("customData"):
        custom = spec.get("customData")
    elif payload is not None:
        custom = encode_payload(payload)
    else:
        custom = spec.get("custom_data") or ""
    marker_id = None
    parsed = _parse_custom(custom) if custom else None
    if parsed:
        marker_id = parsed.get("id")
    existing = serialize_markers(safe(lambda: host.GetMarkers(), {}))
    replaced = False
    if marker_id:
        for row in existing:
            if _payload_id(row.get("customData") or "") == marker_id:
                host.DeleteMarkerAtFrame(row["frame"])
                replaced = True
    ok = host.AddMarker(frame, color, name, note, duration, custom)
    if not ok:
        raise Fail(
            "AddMarker failed.",
            type="MarkerError",
            cause="Resolve returned False.",
            state={"scope": scope, "frame": frame, "color": color, "name": name},
            fix="Check frame range, color name, and that the marker name has no spaces if AddMarker keeps failing.",
        )
    return {
        "success": True,
        "replaced": replaced,
        "scope": scope,
        "frame": frame,
        "color": color,
        "name": name,
        "duration": duration,
        "id": marker_id,
    }


def markers_query(resolve, params=None):
    params = params or {}
    snapshot = inspect(resolve, {"media": params.get("media", "current"), "item_markers": True})
    type_id = params.get("type")
    color = params.get("color")
    scope = params.get("scope")
    start = params.get("start")
    end = params.get("end")
    found = []

    def consider(row, found_scope, extra):
        payload = row.get("payload") or {}
        if type_id and payload.get("type") != type_id and row.get("name") != type_id:
            return
        if color and row.get("color") != color:
            return
        if scope and found_scope != scope:
            return
        frame = row.get("frame")
        if start is not None and frame is not None and frame < start:
            return
        if end is not None and frame is not None and frame >= end:
            return
        item = dict(row)
        item["scope"] = found_scope
        item.update(extra)
        found.append(item)

    tl = (snapshot.get("timeline") or {})
    if tl:
        for row in tl.get("markers") or []:
            consider(row, "timeline", {"timeline": tl.get("name")})
        for track in tl.get("tracks") or []:
            for item in track.get("items") or []:
                for row in item.get("markers") or []:
                    consider(
                        row,
                        "item",
                        {
                            "unique_id": item.get("unique_id"),
                            "clip_name": item.get("name"),
                            "track_type": track.get("type"),
                            "track_index": track.get("index"),
                        },
                    )
    media = snapshot.get("media") or {}
    for clip in media.get("clips") or []:
        for row in clip.get("markers") or []:
            consider(
                row,
                "clip",
                {"media_id": clip.get("media_id"), "clip_name": clip.get("name")},
            )
    return {"markers": found, "count": len(found)}


def markers_clear(resolve, params=None):
    params = params or {}
    host, scope = _marker_host(resolve, params)
    marker_id = params.get("id")
    color = params.get("color")
    frame = params.get("frame")
    deleted = 0
    if marker_id:
        existing = serialize_markers(safe(lambda: host.GetMarkers(), {}))
        for row in existing:
            if _payload_id(row.get("customData") or "") == marker_id:
                if host.DeleteMarkerAtFrame(row["frame"]):
                    deleted += 1
        return {"deleted": deleted, "scope": scope}
    if frame is not None:
        ok = host.DeleteMarkerAtFrame(float(frame))
        return {"deleted": 1 if ok else 0, "scope": scope}
    if color:
        ok = host.DeleteMarkersByColor(color)
        return {"deleted": "unknown" if ok else 0, "scope": scope, "color": color}
    raise Fail("Provide id, frame, or color to clear markers.", type="MarkerError")


def set_clip_color(resolve, params=None):
    params = params or {}
    color = _normalize_clip_color(params.get("color"))
    _, _, tl = _timeline(resolve)
    unique_ids = params.get("unique_ids") or []
    media_id = params.get("media_id")
    clip_name = params.get("clip_name") or params.get("name")
    changed = []
    for track_type in ("video", "audio"):
        count = int(safe(lambda t=track_type: tl.GetTrackCount(t), 0) or 0)
        for index in range(1, count + 1):
            items = safe(lambda t=track_type, i=index: tl.GetItemListInTrack(t, i), []) or []
            for item in items:
                uid = safe(lambda it=item: it.GetUniqueId()) or ""
                mp = safe(lambda it=item: it.GetMediaPoolItem())
                mid = safe(lambda m=mp: m.GetMediaId()) if mp else ""
                iname = safe(lambda it=item: it.GetName()) or ""
                match = False
                if unique_ids:
                    match = uid in unique_ids
                elif media_id and media_id == mid:
                    match = True
                elif clip_name and clip_name == iname:
                    match = True
                elif not unique_ids and not media_id and not clip_name:
                    match = True
                if not match:
                    continue
                if color:
                    ok = item.SetClipColor(color)
                else:
                    ok = item.ClearClipColor()
                changed.append({"unique_id": uid, "name": iname, "color": color or "", "success": bool(ok)})
    if not changed:
        raise Fail("No matching timeline clips to color.", type="PlacementError")
    return {"changed": changed, "count": len(changed)}


def clip_metadata_get(resolve, params=None):
    params = params or {}
    _, pool = _pool(resolve)
    clip = find_clip(pool, params)
    if not clip:
        raise Fail("Clip not found.", type="MarkerError", state={"params": json_safe(params)})
    return _inspect_clip(clip, include_metadata=True)


def clip_metadata_set(resolve, params=None):
    params = params or {}
    _, pool = _pool(resolve)
    clip = find_clip(pool, params)
    if not clip:
        raise Fail("Clip not found.", type="MarkerError")
    metadata = params.get("metadata") or {}
    third = params.get("third_party") or params.get("thirdParty") or {}
    ok_meta = True
    ok_third = True
    if metadata:
        ok_meta = bool(clip.SetMetadata(metadata))
    if third:
        ok_third = bool(clip.SetThirdPartyMetadata(third))
    return {"success": bool(ok_meta and ok_third), "clip": _inspect_clip(clip)}


METHODS = {
    "ping": ping,
    "inspect": inspect,
    "import_media": import_media,
    "ensure_timeline": ensure_timeline,
    "place": place,
    "lift": lift,
    "marker_upsert": marker_upsert,
    "markers_query": markers_query,
    "markers_clear": markers_clear,
    "clip_metadata_get": clip_metadata_get,
    "clip_metadata_set": clip_metadata_set,
    "set_clip_color": set_clip_color,
}


def dispatch(resolve, method, params=None):
    fn = METHODS.get(method)
    if not fn:
        return {
            "ok": False,
            "error": Fail(
                "Unknown method '%s'." % method,
                type="UnknownMethod",
                fix="Re-click Workspace > Scripts > Utility > video_harness_bridge after install-bridge.",
            ).to_dict(),
        }
    try:
        result = fn(resolve, params or {})
        return {"ok": True, "result": json_safe(result)}
    except Fail as exc:
        return {"ok": False, "error": exc.to_dict()}
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "type": "ResolveError",
                "message": str(exc),
                "cause": traceback.format_exc(),
                "fix": "See cause; Resolve API calls often return None on failure.",
                "state": {"method": method},
            },
        }


if __name__ == "__main__":
    print("vh_runtime is a library. Launch video_harness_bridge from Workspace > Scripts.")
