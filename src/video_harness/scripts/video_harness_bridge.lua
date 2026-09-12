--[[
  video_harness_bridge.lua
  Launch from: Workspace > Scripts > Utility > video_harness_bridge
  (Lua always lists. Python .py files stay hidden until Resolve finds Python.)

  File-queue RPC: ~/.config/video-harness/rpc/request.json -> response.json
  Leave this script running.
]]

local MARKER_SCHEMA = "video-harness.marker/v1"
local BRIDGE_VERSION = "0.1.1"
local METHOD_NAMES = {
    "ping",
    "inspect",
    "import_media",
    "ensure_timeline",
    "place",
    "marker_upsert",
    "set_clip_color",
    "insert_title",
    "insert_generator",
    "set_timecode",
    "add_transition",
    "set_item_property",
    "overlay_fusion_title",
    "apply_lut",
}

local function home_dir()
    return os.getenv("HOME") or os.getenv("USERPROFILE") or "."
end

local function join(a, b)
    -- Fusion 21.1 may leave `package` nil; do not use package.config.
    local sep = "/"
    local home = os.getenv("HOME") or os.getenv("USERPROFILE") or ""
    if home:find("\\") or (os.getenv("OS") or ""):find("Windows") then
        sep = "\\"
    end
    if a:sub(-1) == sep then
        return a .. b
    end
    return a .. sep .. b
end

local CFG_DIR = join(home_dir(), ".config/video-harness")
local RPC_DIR = join(CFG_DIR, "rpc")
local REQ_PATH = join(RPC_DIR, "request.json")
local RES_PATH = join(RPC_DIR, "response.json")
local HB_PATH = join(CFG_DIR, "bridge-heartbeat.json")
local CFG_PATH = join(CFG_DIR, "bridge.json")
local LOG_PATH = join(CFG_DIR, "bridge.log")

local function log(msg)
    local f = io.open(LOG_PATH, "a")
    if f then
        f:write(os.date("%Y-%m-%d %H:%M:%S") .. " " .. tostring(msg) .. "\n")
        f:close()
    end
    print("[video-harness-bridge] " .. tostring(msg))
end

local function mkdir_p(path)
    -- Sandboxed Resolve cannot os.execute. Best-effort: create by writing a keep file
    -- after the host installer has created CFG_DIR.
    local marker = join(path, ".keep")
    local f = io.open(marker, "a")
    if f then
        f:close()
    end
end

local function read_file(path)
    local f = io.open(path, "rb")
    if not f then
        return nil
    end
    local data = f:read("*a")
    f:close()
    return data
end

local function write_file(path, data)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, "wb")
    if not f then
        return false
    end
    f:write(data)
    f:close()
    os.remove(path)
    return os.rename(tmp, path) ~= nil or write_file_direct(path, data)
end

function write_file_direct(path, data)
    local f = io.open(path, "wb")
    if not f then
        return false
    end
    f:write(data)
    f:close()
    return true
end

-- Minimal JSON (objects, arrays, strings, numbers, bool, null)
local function json_escape(s)
    s = tostring(s)
    s = s:gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n"):gsub("\r", "\\r"):gsub("\t", "\\t")
    s = s:gsub("[%z\1-\31]", function(c)
        return string.format("\\u%04x", string.byte(c))
    end)
    return '"' .. s .. '"'
end

local function is_array(t)
    local n = 0
    local maxn = 0
    for k, _ in pairs(t) do
        if type(k) ~= "number" then
            return false
        end
        n = n + 1
        if k > maxn then
            maxn = k
        end
    end
    -- empty table is an object so missing project/timeline keys can be {}
    if n == 0 then
        return false
    end
    return n == maxn
end

local function json_encode(v)
    local tv = type(v)
    if v == nil then
        return "null"
    elseif tv == "boolean" then
        return v and "true" or "false"
    elseif tv == "number" then
        return tostring(v)
    elseif tv == "string" then
        return json_escape(v)
    elseif tv == "table" then
        if is_array(v) then
            local parts = {}
            for i = 1, #v do
                parts[i] = json_encode(v[i])
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, val in pairs(v) do
                if val ~= nil and type(val) ~= "function" and type(val) ~= "userdata" and type(val) ~= "thread" then
                    parts[#parts + 1] = json_escape(tostring(k)) .. ":" .. json_encode(val)
                elseif type(val) == "userdata" then
                    parts[#parts + 1] = json_escape(tostring(k)) .. ":" .. json_escape(tostring(val))
                end
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    elseif tv == "userdata" or tv == "function" then
        return json_escape(tostring(v))
    end
    return json_escape(tostring(v))
end

local function json_decode(str)
    if bmd and bmd.parseJSON then
        local ok, val = pcall(bmd.parseJSON, str)
        if ok then
            return val
        end
    end
    local i = 1
    local s = str
    local function peek()
        return s:sub(i, i)
    end
    local function skip()
        while s:sub(i, i):match("%s") do
            i = i + 1
        end
    end
    local parse_value
    local function parse_string()
        i = i + 1
        local out = {}
        while true do
            local c = s:sub(i, i)
            if c == "" then
                error("unterminated string")
            elseif c == '"' then
                i = i + 1
                return table.concat(out)
            elseif c == "\\" then
                local n = s:sub(i + 1, i + 1)
                local map = { n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\" }
                out[#out + 1] = map[n] or n
                i = i + 2
            else
                out[#out + 1] = c
                i = i + 1
            end
        end
    end
    local function parse_number()
        local j = s:match("^%-?%d+%.?%d*[eE]?[%+%-]?%d*", i)
        i = i + #j
        return tonumber(j)
    end
    local function parse_array()
        i = i + 1
        local arr = {}
        skip()
        if peek() == "]" then
            i = i + 1
            return arr
        end
        while true do
            arr[#arr + 1] = parse_value()
            skip()
            if peek() == "]" then
                i = i + 1
                return arr
            elseif peek() == "," then
                i = i + 1
                skip()
            else
                error("bad array")
            end
        end
    end
    local function parse_object()
        i = i + 1
        local obj = {}
        skip()
        if peek() == "}" then
            i = i + 1
            return obj
        end
        while true do
            skip()
            local key = parse_string()
            skip()
            if peek() ~= ":" then
                error("expected :")
            end
            i = i + 1
            obj[key] = parse_value()
            skip()
            if peek() == "}" then
                i = i + 1
                return obj
            elseif peek() == "," then
                i = i + 1
            else
                error("bad object")
            end
        end
    end
    parse_value = function()
        skip()
        local c = peek()
        if c == '"' then
            return parse_string()
        elseif c == "{" then
            return parse_object()
        elseif c == "[" then
            return parse_array()
        elseif c == "t" and s:sub(i, i + 3) == "true" then
            i = i + 4
            return true
        elseif c == "f" and s:sub(i, i + 4) == "false" then
            i = i + 5
            return false
        elseif c == "n" and s:sub(i, i + 3) == "null" then
            i = i + 4
            return nil
        else
            return parse_number()
        end
    end
    return parse_value()
end

local function load_token()
    local raw = read_file(CFG_PATH)
    if not raw then
        return ""
    end
    local ok, cfg = pcall(json_decode, raw)
    if ok and type(cfg) == "table" then
        return cfg.token or ""
    end
    return ""
end

local function get_resolve()
    if resolve then
        return resolve
    end
    if type(Resolve) == "function" then
        local ok, r = pcall(Resolve)
        if ok and r then
            return r
        end
    end
    if fusion and fusion.GetResolve then
        local ok, r = pcall(function()
            return fusion:GetResolve()
        end)
        if ok and r then
            return r
        end
    end
    if fu and fu.GetResolve then
        local ok, r = pcall(function()
            return fu:GetResolve()
        end)
        if ok and r then
            return r
        end
    end
    if bmd and bmd.scriptapp then
        local ok, r = pcall(bmd.scriptapp, "Resolve")
        if ok and r then
            return r
        end
    end
    return nil
end

local function safe(fn, default)
    local ok, val = pcall(fn)
    if ok and val ~= nil then
        return val
    end
    return default
end

local function fail(message, typ, extra)
    extra = extra or {}
    extra.type = typ or "HarnessError"
    extra.message = message
    error(extra, 0)
end

local function project_of(r)
    local pm = r:GetProjectManager()
    if not pm then
        fail("No project manager.", "ConnectionError")
    end
    local proj = pm:GetCurrentProject()
    if not proj then
        fail("No project is open.", "NoProjectError")
    end
    return pm, proj
end

local function timeline_of(r)
    local pm, proj = project_of(r)
    local tl = proj:GetCurrentTimeline()
    if not tl then
        fail("No timeline is current.", "NoTimelineError")
    end
    return pm, proj, tl
end

local function iter_folders(folder, acc)
    acc = acc or {}
    acc[#acc + 1] = folder
    local subs = safe(function()
        return folder:GetSubFolderList()
    end, {}) or {}
    for _, sub in pairs(subs) do
        iter_folders(sub, acc)
    end
    return acc
end

local function clip_path(clip)
    local props = safe(function()
        return clip:GetClipProperty()
    end, {}) or {}
    return props["File Path"] or props["FilePath"] or ""
end

local function find_clip(pool, params)
    local media_id = params.media_id or params.mediaId
    local unique_id = params.unique_id or params.uniqueId
    local name = params.clip_name or params.clipName
    local path = params.path or params.filePath
    local root = pool:GetRootFolder()
    if not root then
        return nil
    end
    for _, folder in ipairs(iter_folders(root)) do
        local clips = safe(function()
            return folder:GetClipList()
        end, {}) or {}
        for _, clip in pairs(clips) do
            if media_id and safe(function()
                return clip:GetMediaId()
            end) == media_id then
                return clip
            end
            if unique_id and safe(function()
                return clip:GetUniqueId()
            end) == unique_id then
                return clip
            end
            if path ~= nil and path ~= "" and clip_path(clip) == path then
                return clip
            end
            if name and safe(function()
                return clip:GetName()
            end) == name then
                return clip
            end
        end
    end
    return nil
end

local function parse_custom(custom)
    if type(custom) ~= "string" or custom == "" then
        return nil
    end
    local ok, data = pcall(json_decode, custom)
    if ok and type(data) == "table" then
        return data
    end
    return nil
end

local function serialize_markers(raw)
    local out = {}
    if not raw then
        return out
    end
    for frame, info in pairs(raw) do
        local row = {}
        if type(info) == "table" then
            for k, v in pairs(info) do
                row[k] = v
            end
        end
        row.frame = tonumber(frame)
        local parsed = parse_custom(row.customData)
        if parsed then
            row.payload = parsed
        end
        out[#out + 1] = row
    end
    table.sort(out, function(a, b)
        return (a.frame or 0) < (b.frame or 0)
    end)
    return out
end

local function sval(v)
    if v == nil then
        return ""
    end
    local s = tostring(v)
    -- Strip leftover control chars so inspect JSON stays strict.
    s = s:gsub("[%z\1-\8\11\12\14-\31]", " ")
    return s
end

local function clip_prop(clip, key)
    local all = safe(function()
        return clip:GetClipProperty()
    end)
    if type(all) == "table" and all[key] ~= nil and all[key] ~= "" then
        return sval(all[key])
    end
    local one = safe(function()
        return clip:GetClipProperty(key)
    end)
    if one ~= nil and one ~= "" and type(one) ~= "table" then
        return sval(one)
    end
    return ""
end

local function inspect_clip(clip, include_metadata)
    local row = {
        name = sval(safe(function()
            return clip:GetName()
        end)) or clip_prop(clip, "Clip Name"),
        media_id = sval(safe(function()
            return clip:GetMediaId()
        end)),
        unique_id = sval(safe(function()
            return clip:GetUniqueId()
        end)),
        path = clip_prop(clip, "File Path"),
        fps = clip_prop(clip, "FPS"),
        frames = clip_prop(clip, "Frames"),
        duration = clip_prop(clip, "Duration"),
        color = sval(safe(function()
            return clip:GetClipColor()
        end)),
        type = clip_prop(clip, "Type"),
        markers = serialize_markers(safe(function()
            return clip:GetMarkers()
        end, {})),
    }
    if row.name == "" then
        row.name = clip_prop(clip, "Clip Name")
    end
    if include_metadata then
        local md = safe(function()
            return clip:GetMetadata()
        end, {})
        row.metadata = type(md) == "table" and md or {}
        local tp = safe(function()
            return clip:GetThirdPartyMetadata()
        end, {})
        row.third_party = type(tp) == "table" and tp or {}
    end
    return row
end

local function inspect_timeline(tl)
    local tracks = {}
    local types = { "video", "audio", "subtitle" }
    for _, track_type in ipairs(types) do
        local count = tonumber(safe(function()
            return tl:GetTrackCount(track_type)
        end, 0)) or 0
        for index = 1, count do
            local items_out = {}
            local items = safe(function()
                return tl:GetItemListInTrack(track_type, index)
            end, {}) or {}
            for _, item in pairs(items) do
                local mp = safe(function()
                    return item:GetMediaPoolItem()
                end)
                items_out[#items_out + 1] = {
                    name = sval(safe(function()
                        return item:GetName()
                    end)),
                    unique_id = sval(safe(function()
                        return item:GetUniqueId()
                    end)),
                    start = safe(function()
                        return item:GetStart()
                    end),
                    ["end"] = safe(function()
                        return item:GetEnd()
                    end),
                    duration = safe(function()
                        return item:GetDuration()
                    end),
                    source_start = safe(function()
                        return item:GetSourceStartFrame()
                    end),
                    source_end = safe(function()
                        return item:GetSourceEndFrame()
                    end),
                    color = sval(safe(function()
                        return item:GetClipColor()
                    end)),
                    media_id = mp and sval(safe(function()
                        return mp:GetMediaId()
                    end)) or nil,
                    media_name = mp and sval(safe(function()
                        return mp:GetName()
                    end)) or nil,
                    path = mp and sval(clip_path(mp)) or "",
                    markers = serialize_markers(safe(function()
                        return item:GetMarkers()
                    end, {})),
                }
            end
            tracks[#tracks + 1] = {
                type = track_type,
                index = index,
                name = safe(function()
                    return tl:GetTrackName(track_type, index)
                end),
                items = items_out,
            }
        end
    end
    return {
        name = safe(function()
            return tl:GetName()
        end),
        unique_id = safe(function()
            return tl:GetUniqueId()
        end),
        start_frame = safe(function()
            return tl:GetStartFrame()
        end),
        end_frame = safe(function()
            return tl:GetEndFrame()
        end),
        start_timecode = safe(function()
            return tl:GetStartTimecode()
        end),
        current_timecode = safe(function()
            return tl:GetCurrentTimecode()
        end),
        fps = safe(function()
            return tl:GetSetting("timelineFrameRate")
        end),
        markers = serialize_markers(safe(function()
            return tl:GetMarkers()
        end, {})),
        tracks = tracks,
    }
end

local function ping(r)
    return {
        ok = true,
        product = safe(function()
            return r:GetProductName()
        end),
        version = safe(function()
            return r:GetVersionString()
        end),
        page = safe(function()
            return r:GetCurrentPage()
        end),
        bridge = BRIDGE_VERSION,
        transport = "lua-file",
        methods = METHOD_NAMES,
    }
end

local function inspect(r, params)
    params = params or {}
    local result = { app = ping(r), project = nil, timeline = nil, media = nil }
    local pm = safe(function()
        return r:GetProjectManager()
    end)
    local proj = pm and safe(function()
        return pm:GetCurrentProject()
    end)
    if not proj then
        return result
    end
    result.project = {
        name = safe(function()
            return proj:GetName()
        end),
        timeline_count = safe(function()
            return proj:GetTimelineCount()
        end, 0),
        fps = safe(function()
            return proj:GetSetting("timelineFrameRate")
        end),
        width = safe(function()
            return proj:GetSetting("timelineResolutionWidth")
        end),
        height = safe(function()
            return proj:GetSetting("timelineResolutionHeight")
        end),
    }
    local tl = safe(function()
        return proj:GetCurrentTimeline()
    end)
    if tl then
        result.timeline = inspect_timeline(tl)
    end
    local pool = safe(function()
        return proj:GetMediaPool()
    end)
    local media_mode = params.media or "current"
    if pool then
        local current = safe(function()
            return pool:GetCurrentFolder()
        end)
        local folder_name = current and safe(function()
            return current:GetName()
        end) or nil
        if media_mode == "none" then
            result.media = { current_folder = folder_name, clip_count = 0, clips = {} }
        else
            local root = safe(function()
                return pool:GetRootFolder()
            end)
            local clips = {}
            local folders = {}
            if media_mode == "all" and root then
                folders = iter_folders(root)
            elseif current then
                folders = { current }
            elseif root then
                folders = { root }
            end
            for _, folder in ipairs(folders) do
                local list = safe(function()
                    return folder:GetClipList()
                end, {}) or {}
                for _, clip in pairs(list) do
                    clips[#clips + 1] = inspect_clip(clip, true)
                end
            end
            result.media = {
                current_folder = folder_name,
                clip_count = #clips,
                clips = clips,
            }
        end
    end
    return result
end

local function import_media(r, params)
    local paths = params.paths or params.filePaths
    if not paths or #paths == 0 then
        fail("paths is required.", "PlacementError")
    end
    local _, proj = project_of(r)
    local pool = proj:GetMediaPool()
    local items = pool:ImportMedia(paths)
    if not items then
        fail("ImportMedia returned nothing.", "PlacementError")
    end
    local imported = {}
    for _, item in pairs(items) do
        imported[#imported + 1] = inspect_clip(item, false)
    end
    return { imported = imported, count = #imported }
end

local function ensure_timeline(r, params)
    local name = params.name
    local _, proj = project_of(r)
    if name and name ~= "" then
        local count = tonumber(safe(function()
            return proj:GetTimelineCount()
        end, 0)) or 0
        for index = 1, count do
            local tl = proj:GetTimelineByIndex(index)
            if tl and safe(function()
                return tl:GetName()
            end) == name then
                proj:SetCurrentTimeline(tl)
                return { name = name, created = false, switched = true }
            end
        end
        local pool = proj:GetMediaPool()
        local tl = pool:CreateEmptyTimeline(name)
        if not tl then
            fail("Failed to create timeline '" .. name .. "'.", "PlacementError")
        end
        proj:SetCurrentTimeline(tl)
        return { name = name, created = true, switched = true }
    end
    local _, _, tl = timeline_of(r)
    return {
        name = safe(function()
            return tl:GetName()
        end),
        created = false,
        switched = false,
    }
end

local function ensure_track(tl, track_type, index)
    track_type = track_type or "video"
    index = tonumber(index or 1)
    local count = tonumber(safe(function()
        return tl:GetTrackCount(track_type)
    end, 0)) or 0
    while count < index do
        if not tl:AddTrack(track_type) then
            fail("Could not add track.", "PlacementError")
        end
        count = tonumber(tl:GetTrackCount(track_type)) or count + 1
    end
    return index
end

local function place(r, params)
    local items = params.items or {}
    if #items == 0 then
        fail("items is required.", "PlacementError")
    end
    local _, proj, tl = timeline_of(r)
    local pool = proj:GetMediaPool()
    local clip_infos = {}
    for _, spec in ipairs(items) do
        local lookup = spec
        if spec.name and not spec.clip_name and not spec.media_id then
            lookup = {}
            for k, v in pairs(spec) do
                lookup[k] = v
            end
            lookup.clip_name = spec.name
        end
        local clip = find_clip(pool, lookup)
        if not clip then
            fail("Could not find clip in the media pool.", "PlacementError")
        end
        local track_index = ensure_track(tl, spec.track_type or spec.trackType or "video", spec.track_index or spec.trackIndex or 1)
        local info = { mediaPoolItem = clip, trackIndex = track_index }
        if spec.record_frame ~= nil or spec.recordFrame ~= nil then
            info.recordFrame = spec.record_frame or spec.recordFrame
        end
        if spec.source_in ~= nil or spec.startFrame ~= nil then
            info.startFrame = spec.source_in or spec.startFrame
        end
        if spec.source_out ~= nil or spec.endFrame ~= nil then
            info.endFrame = spec.source_out or spec.endFrame
        end
        if spec.media_type ~= nil or spec.mediaType ~= nil then
            info.mediaType = spec.media_type or spec.mediaType
        end
        clip_infos[#clip_infos + 1] = info
    end
    local placed = pool:AppendToTimeline(clip_infos)
    if not placed then
        fail("AppendToTimeline returned nothing.", "PlacementError")
    end
    local out = {}
    for _, item in pairs(placed) do
        out[#out + 1] = {
            name = safe(function()
                return item:GetName()
            end),
            unique_id = safe(function()
                return item:GetUniqueId()
            end),
            start = safe(function()
                return item:GetStart()
            end),
            ["end"] = safe(function()
                return item:GetEnd()
            end),
        }
    end
    return { placed = out, count = #out }
end

local function marker_host(r, spec)
    local scope = spec.scope or "timeline"
    local _, proj, tl = timeline_of(r)
    if scope == "timeline" then
        return tl, "timeline"
    elseif scope == "item" then
        local uid = spec.unique_id or spec.uniqueId
        if not uid then
            fail("unique_id is required for item-scope markers.", "MarkerError")
        end
        for _, track_type in ipairs({ "video", "audio", "subtitle" }) do
            local count = tonumber(safe(function()
                return tl:GetTrackCount(track_type)
            end, 0)) or 0
            for index = 1, count do
                local items = safe(function()
                    return tl:GetItemListInTrack(track_type, index)
                end, {}) or {}
                for _, item in pairs(items) do
                    if safe(function()
                        return item:GetUniqueId()
                    end) == uid then
                        return item, "item"
                    end
                end
            end
        end
        fail("Timeline item not found.", "MarkerError")
    elseif scope == "clip" then
        local pool = proj:GetMediaPool()
        local clip = find_clip(pool, spec)
        if not clip then
            fail("Media pool clip not found.", "MarkerError")
        end
        return clip, "clip"
    end
    fail("Unknown marker scope.", "MarkerError")
end

local function encode_payload(payload)
    payload = payload or {}
    if not payload.schema then
        payload.schema = MARKER_SCHEMA
    end
    return json_encode(payload)
end

local function upsert_one(r, spec)
    local host, scope = marker_host(r, spec)
    local frame = spec.frame
    if frame == nil then
        fail("frame is required.", "MarkerError")
    end
    local color = spec.color or "Blue"
    local name = spec.name or spec.type or "mark"
    local note = spec.note or ""
    local duration = spec.duration or 1
    local custom = spec.customData or spec.custom_data or ""
    if spec.payload ~= nil then
        custom = encode_payload(spec.payload)
    end
    local marker_id = nil
    local parsed = parse_custom(custom)
    if parsed then
        marker_id = parsed.id
    end
    local replaced = false
    if marker_id then
        local existing = serialize_markers(safe(function()
            return host:GetMarkers()
        end, {}))
        for _, row in ipairs(existing) do
            local p = parse_custom(row.customData or "")
            if p and p.id == marker_id then
                host:DeleteMarkerAtFrame(row.frame)
                replaced = true
            end
        end
    end
    local ok = host:AddMarker(frame, color, name, note, duration, custom)
    if not ok then
        fail("AddMarker failed.", "MarkerError")
    end
    return {
        success = true,
        replaced = replaced,
        scope = scope,
        frame = frame,
        color = color,
        name = name,
        duration = duration,
        id = marker_id,
    }
end

local function marker_upsert(r, params)
    local markers = params.markers
    if markers == nil then
        markers = { params }
    end
    local results = {}
    for _, spec in ipairs(markers) do
        results[#results + 1] = upsert_one(r, spec)
    end
    return { markers = results, count = #results }
end

local CLIP_COLORS = {
    Orange = true,
    Apricot = true,
    Yellow = true,
    Lime = true,
    Olive = true,
    Green = true,
    Teal = true,
    Navy = true,
    Blue = true,
    Purple = true,
    Violet = true,
    Pink = true,
    Tan = true,
    Beige = true,
    Brown = true,
    Chocolate = true,
}
local CLIP_COLOR_ALIASES = {
    Cyan = "Teal",
    Mint = "Lime",
    Red = "Violet",
    Crimson = "Violet",
    Sky = "Navy",
    Fuchsia = "Pink",
    Magenta = "Pink",
    Lemon = "Yellow",
    Lavender = "Purple",
    Rose = "Pink",
    Sand = "Tan",
    Cocoa = "Chocolate",
    Cream = "Beige",
    White = "Beige",
}

local function resolve_clip_color(color)
    if color == nil or color == "" then
        return ""
    end
    color = tostring(color)
    if CLIP_COLORS[color] then
        return color
    end
    local lower = string.lower(color)
    for name, _ in pairs(CLIP_COLORS) do
        if string.lower(name) == lower then
            return name
        end
    end
    for src, dst in pairs(CLIP_COLOR_ALIASES) do
        if string.lower(src) == lower then
            return dst
        end
    end
    fail(
        "Invalid clip color '"
            .. color
            .. "'. Valid: Orange, Apricot, Yellow, Lime, Olive, Green, Teal, Navy, Blue, Purple, Violet, Pink, Tan, Beige, Brown, Chocolate. Aliases: Cyan→Teal, Mint→Lime, Red→Violet.",
        "PlacementError"
    )
end

local function set_clip_color(r, params)
    local color = resolve_clip_color(params.color)
    local _, _, tl = timeline_of(r)
    local unique_ids = params.unique_ids or {}
    local media_id = params.media_id
    local clip_name = params.clip_name or params.name
    local changed = {}
    for _, track_type in ipairs({ "video", "audio" }) do
        local count = tonumber(safe(function()
            return tl:GetTrackCount(track_type)
        end, 0)) or 0
        for index = 1, count do
            local items = safe(function()
                return tl:GetItemListInTrack(track_type, index)
            end, {}) or {}
            for _, item in pairs(items) do
                local uid = sval(safe(function()
                    return item:GetUniqueId()
                end))
                local mp = safe(function()
                    return item:GetMediaPoolItem()
                end)
                local mid = mp and sval(safe(function()
                    return mp:GetMediaId()
                end)) or ""
                local iname = sval(safe(function()
                    return item:GetName()
                end))
                local match = false
                if #unique_ids > 0 then
                    for _, want in ipairs(unique_ids) do
                        if want == uid then
                            match = true
                        end
                    end
                elseif media_id and media_id == mid then
                    match = true
                elseif clip_name and clip_name == iname then
                    match = true
                elseif (not unique_ids or #unique_ids == 0) and not media_id and not clip_name then
                    match = true
                end
                if match then
                    local ok
                    if color and color ~= "" then
                        ok = item:SetClipColor(color)
                    else
                        ok = item:ClearClipColor()
                    end
                    changed[#changed + 1] = {
                        unique_id = uid,
                        name = iname,
                        color = color or "",
                        success = not not ok,
                    }
                end
            end
        end
    end
    if #changed == 0 then
        fail("No matching timeline clips to color.", "PlacementError")
    end
    return { changed = changed, count = #changed }
end

local function set_timecode(r, params)
    local _, _, tl = timeline_of(r)
    local tc = params.timecode or params.tc
    if not tc then
        fail("timecode is required.", "PlacementError")
    end
    local ok = tl:SetCurrentTimecode(tostring(tc))
    return { success = not not ok, timecode = tostring(tc) }
end

local function _set_fusion_text(item, text)
    if not item or not text or text == "" then
        return false
    end
    safe(function()
        item:SetName(text)
    end)
    local count = tonumber(safe(function()
        return item:GetFusionCompCount()
    end, 0)) or 0
    if count < 1 then
        return false
    end
    local comp = safe(function()
        return item:GetFusionCompByIndex(1)
    end)
    if not comp then
        return false
    end
    local names = { "Text1", "TextPlus1", "Template", "Title", "Text+" }
    for _, name in ipairs(names) do
        local tool = safe(function()
            return comp:FindTool(name)
        end)
        if tool then
            safe(function()
                tool.StyledText = text
            end)
            return true
        end
    end
    local tools = safe(function()
        return comp:GetToolList(false)
    end)
    if type(tools) == "table" then
        for _, tool in pairs(tools) do
            if tool and tool.StyledText ~= nil then
                safe(function()
                    tool.StyledText = text
                end)
                return true
            end
        end
    end
    return false
end

local function insert_title(r, params)
    local _, _, tl = timeline_of(r)
    local title_type = params.title_type or "text_plus"
    local title_name = params.title_name or params.name or "Text+"
    if params.timecode or params.tc then
        tl:SetCurrentTimecode(tostring(params.timecode or params.tc))
    end
    local item = nil
    if title_type == "fusion" or title_type == "text_plus" then
        item = safe(function()
            return tl:InsertFusionTitleIntoTimeline(title_name)
        end)
    else
        item = safe(function()
            return tl:InsertTitleIntoTimeline(title_name)
        end)
    end
    if not item then
        fail("Failed to insert title '" .. tostring(title_name) .. "' into timeline.", "PlacementError")
    end
    local text = params.text or params.styled_text
    local text_ok = false
    if text then
        text_ok = _set_fusion_text(item, text)
    end
    return {
        success = true,
        title_name = title_name,
        title_type = title_type,
        text = text or "",
        text_applied = text_ok,
        unique_id = sval(safe(function()
            return item:GetUniqueId()
        end)),
        name = sval(safe(function()
            return item:GetName()
        end)),
        start = safe(function()
            return item:GetStart()
        end),
        ["end"] = safe(function()
            return item:GetEnd()
        end),
    }
end

local function add_transition(r, params)
    local _, _, tl = timeline_of(r)
    local duration = tonumber(params.duration or params.duration_frames or 12) or 12
    local ttype = params.transition or params.type or "Cross Dissolve"
    local unique_ids = params.unique_ids or {}
    local applied = {}
    local skipped = {}
    local tracks = { "video" }
    if params.audio then
        tracks[#tracks + 1] = "audio"
    end
    for _, track_type in ipairs(tracks) do
        local count = tonumber(safe(function()
            return tl:GetTrackCount(track_type)
        end, 0)) or 0
        for index = 1, count do
            local items = safe(function()
                return tl:GetItemListInTrack(track_type, index)
            end, {}) or {}
            local ordered = {}
            for _, item in pairs(items) do
                ordered[#ordered + 1] = item
            end
            table.sort(ordered, function(a, b)
                return (tonumber(safe(function()
                    return a:GetStart()
                end, 0)) or 0) < (tonumber(safe(function()
                    return b:GetStart()
                end, 0)) or 0)
            end)
            for i = 1, #ordered - 1 do
                local item = ordered[i]
                local uid = sval(safe(function()
                    return item:GetUniqueId()
                end))
                local want = true
                if #unique_ids > 0 then
                    want = false
                    for _, w in ipairs(unique_ids) do
                        if w == uid then
                            want = true
                        end
                    end
                end
                if want then
                    local ok = safe(function()
                        if item.AddTransition then
                            return item:AddTransition({
                                type = ttype,
                                category = params.category or "simple",
                                position = params.position or "end",
                                alignment = params.alignment or "center",
                                duration = duration,
                            })
                        end
                        return nil
                    end)
                    if ok then
                        applied[#applied + 1] = { unique_id = uid, transition = ttype, duration = duration }
                    else
                        skipped[#skipped + 1] = { unique_id = uid, reason = "AddTransition missing or rejected (need handles / Studio 21.1+)" }
                    end
                end
            end
        end
    end
    return { applied = applied, skipped = skipped, count = #applied }
end

local function set_item_property(r, params)
    local _, _, tl = timeline_of(r)
    local key = params.key or params.property
    local value = params.value
    if not key then
        fail("key is required.", "PlacementError")
    end
    local unique_ids = params.unique_ids or {}
    local clip_name = params.clip_name or params.name
    local changed = {}
    for _, track_type in ipairs({ "video", "audio" }) do
        local count = tonumber(safe(function()
            return tl:GetTrackCount(track_type)
        end, 0)) or 0
        for index = 1, count do
            local items = safe(function()
                return tl:GetItemListInTrack(track_type, index)
            end, {}) or {}
            for _, item in pairs(items) do
                local uid = sval(safe(function()
                    return item:GetUniqueId()
                end))
                local iname = sval(safe(function()
                    return item:GetName()
                end))
                local match = false
                if #unique_ids > 0 then
                    for _, w in ipairs(unique_ids) do
                        if w == uid then
                            match = true
                        end
                    end
                elseif clip_name and clip_name == iname then
                    match = true
                elseif #unique_ids == 0 and not clip_name then
                    match = true
                end
                if match then
                    local ok = safe(function()
                        return item:SetProperty(key, value)
                    end)
                    changed[#changed + 1] = {
                        unique_id = uid,
                        name = iname,
                        key = key,
                        success = not not ok,
                    }
                end
            end
        end
    end
    return { changed = changed, count = #changed }
end

local function find_timeline_item(tl, unique_id)
    for _, track_type in ipairs({ "video", "audio" }) do
        local count = tonumber(safe(function()
            return tl:GetTrackCount(track_type)
        end, 0)) or 0
        for index = 1, count do
            local items = safe(function()
                return tl:GetItemListInTrack(track_type, index)
            end, {}) or {}
            for _, item in pairs(items) do
                local uid = sval(safe(function()
                    return item:GetUniqueId()
                end))
                if uid == unique_id then
                    return item
                end
            end
        end
    end
    return nil
end

local function overlay_fusion_title(r, params)
    -- Title *over* a clip (Fusion Text+ on the item), not a V1 bumper.
    -- Blackmagic TimelineItem.AddFusionComp / Fusion Comp:AddTool("TextPlus").
    local _, _, tl = timeline_of(r)
    local uid = params.unique_id
    local text = params.text
    if not uid or not text or text == "" then
        fail("unique_id and text are required.", "PlacementError")
    end
    local item = find_timeline_item(tl, uid)
    if not item then
        fail("No timeline item with that unique_id.", "PlacementError")
    end
    local comp = safe(function()
        return item:GetFusionCompByIndex(1)
    end)
    if not comp then
        comp = safe(function()
            return item:AddFusionComp()
        end)
    end
    if not comp then
        fail("Could not add a Fusion composition on the clip.", "PlacementError")
    end
    local tool = safe(function()
        return comp:AddTool("TextPlus")
    end)
    if not tool then
        fail("Fusion AddTool TextPlus failed.", "PlacementError")
    end
    local size = tonumber(params.size or 0.07) or 0.07
    local y = tonumber(params.y or 0.2) or 0.2
    safe(function()
        tool.StyledText = text
    end)
    safe(function()
        tool.Size = size
    end)
    safe(function()
        tool.Center = { 0.5, y }
    end)
    return {
        success = true,
        unique_id = uid,
        text = text,
        size = size,
        y = y,
    }
end

local function apply_lut(r, params)
    -- TimelineItem.SetLUT(nodeIndex, lutPath). lutPath should be a Resolve-readable .cube.
    local _, _, tl = timeline_of(r)
    local path = params.path or params.lut or params.lut_path
    if path == nil then
        path = ""
    end
    local node = tonumber(params.node or params.node_index or 1) or 1
    -- Empty path clears the node LUT. Do not slap Film Looks cubes on Rec.709 drone.
    local unique_ids = params.unique_ids or {}
    local changed = {}
    for _, track_type in ipairs({ "video" }) do
        local count = tonumber(safe(function()
            return tl:GetTrackCount(track_type)
        end, 0)) or 0
        for index = 1, count do
            local items = safe(function()
                return tl:GetItemListInTrack(track_type, index)
            end, {}) or {}
            for _, item in pairs(items) do
                local uid = sval(safe(function()
                    return item:GetUniqueId()
                end))
                local iname = sval(safe(function()
                    return item:GetName()
                end))
                if iname ~= "" then
                    local want = true
                    if #unique_ids > 0 then
                        want = false
                        for _, w in ipairs(unique_ids) do
                            if w == uid then
                                want = true
                            end
                        end
                    end
                    if want then
                        local ok = safe(function()
                            return item:SetLUT(node, path)
                        end)
                        changed[#changed + 1] = {
                            unique_id = uid,
                            name = iname,
                            success = not not ok,
                        }
                    end
                end
            end
        end
    end
    return { changed = changed, count = #changed, path = path, node = node }
end

local function insert_generator(r, params)
    local _, _, tl = timeline_of(r)
    local generator_name = params.generator_name or params.name or "Solid Color"
    local item = safe(function()
        return tl:InsertGeneratorIntoTimeline(generator_name)
    end)

    if not item then
        fail("Failed to insert generator '" .. tostring(generator_name) .. "' into timeline.", "PlacementError")
    end

    return {
        success = true,
        generator_name = generator_name,
    }
end

local METHODS = {
    ping = ping,
    inspect = inspect,
    import_media = import_media,
    ensure_timeline = ensure_timeline,
    place = place,
    marker_upsert = marker_upsert,
    set_clip_color = set_clip_color,
    insert_title = insert_title,
    insert_generator = insert_generator,
    set_timecode = set_timecode,
    add_transition = add_transition,
    set_item_property = set_item_property,
    overlay_fusion_title = overlay_fusion_title,
    apply_lut = apply_lut,
}

local function dispatch(r, method, params)
    local fn = METHODS[method]
    if not fn then
        return {
            ok = false,
            error = {
                type = "UnknownMethod",
                message = "Unknown method '" .. tostring(method) .. "'.",
                fix = "install-bridge copies a newer Lua file; re-click Workspace > Scripts > Utility > video_harness_bridge (one instance) so the running script reloads. Do not launch fuscript from a terminal on App Store Lite.",
            },
        }
    end
    local ok, result = pcall(fn, r, params or {})
    if not ok then
        if type(result) == "table" and result.message then
            return { ok = false, error = result }
        end
        return { ok = false, error = { type = "ResolveError", message = tostring(result) } }
    end
    return { ok = true, result = result }
end

local function heartbeat(r)
    local body = {
        ok = r ~= nil,
        ts = os.time(),
        bridge = BRIDGE_VERSION,
        transport = "lua-file",
        methods = METHOD_NAMES,
        product = r and safe(function()
            return r:GetProductName()
        end) or nil,
        version = r and safe(function()
            return r:GetVersionString()
        end) or nil,
    }
    write_file(HB_PATH, json_encode(body))
end

local function poll_once(r, token)
    local raw = read_file(REQ_PATH)
    if not raw or #raw == 0 then
        return r, "idle"
    end
    os.remove(REQ_PATH)
    local ok, request = pcall(json_decode, raw)
    local reply
    if not ok then
        reply = { ok = false, error = { type = "BadRequest", message = "Invalid JSON" } }
    elseif token ~= "" and request.token ~= token then
        reply = { ok = false, id = request.id, error = { type = "AuthError", message = "Bad token" } }
    else
        if not r then
            r = get_resolve()
        end
        reply = dispatch(r, request.method, request.params or {})
        reply.id = request.id
    end
    local encoded_ok, encoded = pcall(json_encode, reply)
    if encoded_ok then
        write_file(RES_PATH, encoded)
    else
        log("json_encode failed: " .. tostring(encoded))
        write_file(RES_PATH, '{"ok":false,"error":{"type":"EncodeError","message":"json_encode failed"}}')
    end
    local method = (type(request) == "table" and request.method) or "?"
    log("handled " .. tostring(method) .. " ok=" .. tostring(reply.ok))
    return r, "handled " .. tostring(method)
end

local function coop_wait(seconds)
    -- Must yield to Resolve's UI. Busy-loops get killed; UIManager is Studio-only (19.1+).
    if bmd and bmd.wait then
        bmd.wait(seconds)
        return true
    end
    if wait then
        wait(seconds)
        return true
    end
    if Wait then
        Wait(seconds)
        return true
    end
    return false
end

local function run_headless(r, token)
    log("headless loop (no UI — UIManager is Studio-only on free Resolve)")
    print("====================================================")
    print("video-harness bridge is RUNNING")
    print("Leave Resolve as-is. Open Workspace > Console for this text.")
    print("Then run: video-harness doctor")
    print("====================================================")
    heartbeat(r)
    local ticks = 0
    while true do
        ticks = ticks + 1
        local ok, err = pcall(function()
            if ticks % 5 == 1 then
                heartbeat(r)
                if not r then
                    r = get_resolve()
                end
            end
            local rr = poll_once(r, token)
            r = rr
        end)
        if not ok then
            log("poll error: " .. tostring(err))
        end
        if not coop_wait(0.2) then
            log("no cooperative wait; exiting after one shot")
            break
        end
    end
    log("loop ended")
end

local function main()
    mkdir_p(CFG_DIR)
    mkdir_p(RPC_DIR)
    local token = load_token()
    local r = get_resolve()
    log("start rpc=" .. RPC_DIR)
    if r then
        log("resolve " .. tostring(safe(function()
            return r:GetProductName()
        end)) .. " " .. tostring(safe(function()
            return r:GetVersionString()
        end)))
    else
        log("WARNING: no Resolve object")
    end
    run_headless(r, token)
end

local ok, err = pcall(main)
if not ok then
    log("FATAL: " .. tostring(err))
    error("video-harness bridge failed: " .. tostring(err))
end
