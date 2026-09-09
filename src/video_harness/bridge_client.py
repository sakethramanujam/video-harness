from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any
from urllib.parse import urljoin

import time
import uuid
from pathlib import Path

from video_harness.errors import ConnectionError, HarnessError
from video_harness.paths import bridge_config_path, config_dir

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore

REQUIRED_LUA_METHODS = (
    "ping",
    "inspect",
    "import_media",
    "ensure_timeline",
    "place",
    "set_clip_color",
)
RELOAD_LUA_FIX = (
    "install-bridge already copied the Lua file. Re-click Workspace > Scripts > "
    "Utility > video_harness_bridge (one instance) so the running script reloads. "
    "Do not launch fuscript from a terminal — App Store Lite kills it."
)

_RPC_THREAD_LOCK = threading.Lock()


def loads_rpc_json(text: str) -> Any:
    """Parse Lua/Python RPC JSON. Accepts (and strips) illegal control characters."""
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        cleaned = "".join(ch if (ord(ch) >= 32 or ch in "\n\r\t") else " " for ch in text)
        return json.loads(cleaned, strict=False)


def _lua_methods_stale(data: dict[str, Any]) -> str | None:
    methods = data.get("methods")
    if not isinstance(methods, list):
        return "Lua bridge did not advertise methods (running script is older than this CLI)."
    missing = [name for name in REQUIRED_LUA_METHODS if name not in methods]
    if missing:
        return "Lua bridge is missing methods: " + ", ".join(missing) + "."
    return None


def load_bridge_config() -> dict[str, Any]:
    path = bridge_config_path()
    if not path.is_file():
        raise ConnectionError(
            f"No bridge config at {path}.",
            fix="Run `video-harness install-bridge`, then start Workspace > Scripts > video_harness_bridge.",
            state={"path": str(path)},
        )
    return json.loads(path.read_text())


class BridgeClient:
    def __init__(self, host: str, port: int, token: str, timeout: float = 120.0) -> None:
        self.base = f"http://{host}:{int(port)}"
        self.token = token
        self.timeout = timeout

    @classmethod
    def from_config(cls) -> BridgeClient:
        cfg = load_bridge_config()
        return cls(
            host=cfg.get("host") or "127.0.0.1",
            port=int(cfg.get("port") or 8765),
            token=cfg.get("token") or "",
        )

    def health(self) -> dict[str, Any]:
        url = urljoin(self.base + "/", "health")
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise ConnectionError(
                f"Bridge is not answering at {url}.",
                cause=str(exc),
                fix="In Resolve: Workspace > Scripts > Utility > video_harness_bridge. Leave it running.",
                state={"url": url},
            ) from exc

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps(
            {"id": 1, "token": self.token, "method": method, "params": params or {}}
        ).encode("utf-8")
        req = urllib.request.Request(
            urljoin(self.base + "/", "rpc"),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except Exception as parse_exc:
                raise ConnectionError(
                    f"Bridge HTTP {exc.code}.",
                    cause=raw[:500],
                    state={"status": exc.code},
                ) from parse_exc
        except Exception as exc:
            raise ConnectionError(
                "Bridge RPC failed.",
                cause=str(exc),
                fix="Confirm the in-app script is still running and no modal dialog is blocking Resolve.",
            ) from exc
        if not body.get("ok"):
            err = body.get("error") or {}
            raise HarnessError(
                err.get("message") or "Bridge call failed.",
                type=err.get("type") or "HarnessError",
                cause=err.get("cause"),
                fix=err.get("fix"),
                state=err.get("state") or {},
            )
        return body.get("result")


class FileBridgeClient:
    """Talk to the Lua in-app script via ~/.config/video-harness/rpc/."""

    def __init__(self, token: str = "", timeout: float = 120.0) -> None:
        self.token = token
        self.timeout = timeout
        self.root = config_dir()
        self.rpc = self.root / "rpc"
        self.req = self.rpc / "request.json"
        self.res = self.rpc / "response.json"
        self.heartbeat = self.root / "bridge-heartbeat.json"

    @classmethod
    def from_config(cls) -> FileBridgeClient:
        token = ""
        try:
            token = load_bridge_config().get("token") or ""
        except ConnectionError:
            pass
        return cls(token=token)

    def health(self) -> dict[str, Any]:
        if not self.heartbeat.is_file():
            raise ConnectionError(
                "Lua bridge heartbeat missing.",
                fix="Workspace > Scripts > Utility > video_harness_bridge (Lua). Leave it running.",
                state={"path": str(self.heartbeat)},
            )
        try:
            data = json.loads(self.heartbeat.read_text())
        except Exception as exc:
            raise ConnectionError("Bad heartbeat file.", cause=str(exc)) from exc
        ts = float(data.get("ts") or 0)
        if time.time() - ts > 8:
            raise ConnectionError(
                "Lua bridge heartbeat is stale.",
                fix="Re-run Workspace > Scripts > Utility > video_harness_bridge.",
                state={"heartbeat": data},
            )
        stale = _lua_methods_stale(data)
        if stale:
            raise ConnectionError(stale, fix=RELOAD_LUA_FIX, state={"heartbeat": data})
        data["ok"] = True
        return data

    @contextmanager
    def _exclusive_rpc(self):
        self.rpc.mkdir(parents=True, exist_ok=True)
        lock_path = self.rpc / "client.lock"
        fh = lock_path.open("a+")
        try:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            fh.close()

    def _wait_request_slot(self, deadline: float) -> None:
        while time.time() < deadline:
            if not self.req.exists() or self.req.stat().st_size == 0:
                return
            time.sleep(0.05)
        try:
            self.req.unlink()
        except OSError:
            pass

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with _RPC_THREAD_LOCK:
            with self._exclusive_rpc():
                return self._call_locked(method, params)

    def _call_locked(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.rpc.mkdir(parents=True, exist_ok=True)
        req_id = str(uuid.uuid4())
        payload = {
            "id": req_id,
            "token": self.token,
            "method": method,
            "params": params or {},
        }
        deadline = time.time() + self.timeout
        self._wait_request_slot(deadline)
        if self.res.exists():
            try:
                self.res.unlink()
            except OSError:
                pass
        tmp = self.req.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(self.req)
        last_stat = None
        stable = 0
        while time.time() < deadline:
            if self.res.is_file():
                try:
                    raw = self.res.read_text(encoding="utf-8", errors="replace")
                    body = loads_rpc_json(raw)
                except Exception:
                    try:
                        stat = (self.res.stat().st_size, self.res.stat().st_mtime)
                    except OSError:
                        time.sleep(0.05)
                        continue
                    if stat == last_stat:
                        stable += 1
                    else:
                        stable = 0
                        last_stat = stat
                    if stable >= 10:
                        raise ConnectionError(
                            "Lua bridge wrote a response that is not valid JSON.",
                            fix=RELOAD_LUA_FIX,
                            state={"path": str(self.res)},
                        )
                    time.sleep(0.05)
                    continue
                if body.get("id") == req_id:
                    try:
                        self.res.unlink()
                    except OSError:
                        pass
                    if not body.get("ok"):
                        err = body.get("error") or {}
                        raise HarnessError(
                            err.get("message") or "Lua bridge call failed.",
                            type=err.get("type") or "HarnessError",
                            cause=err.get("cause"),
                            fix=err.get("fix") or (RELOAD_LUA_FIX if err.get("type") == "UnknownMethod" else None),
                            state=err.get("state") or {},
                        )
                    return body.get("result")
            time.sleep(0.05)
        raise ConnectionError(
            "Lua bridge did not answer in time.",
            fix="Confirm video_harness_bridge.lua is still running (Workspace > Scripts > Utility).",
        )
