from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin

import time
import uuid
from pathlib import Path

from video_harness.errors import ConnectionError, HarnessError
from video_harness.paths import bridge_config_path, config_dir


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
                fix="Workspace > Scripts > Edit > video_harness_bridge (Lua). Leave it running.",
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
                fix="Re-run Workspace > Scripts > Edit > video_harness_bridge.",
                state={"heartbeat": data},
            )
        data["ok"] = True
        return data

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.rpc.mkdir(parents=True, exist_ok=True)
        req_id = str(uuid.uuid4())
        payload = {
            "id": req_id,
            "token": self.token,
            "method": method,
            "params": params or {},
        }
        if self.res.exists():
            self.res.unlink()
        tmp = self.req.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(self.req)
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            if self.res.is_file():
                try:
                    body = json.loads(self.res.read_text())
                except Exception:
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
                            fix=err.get("fix"),
                            state=err.get("state") or {},
                        )
                    return body.get("result")
            time.sleep(0.05)
        raise ConnectionError(
            "Lua bridge did not answer in time.",
            fix="Confirm video_harness_bridge.lua is still running (Workspace > Scripts > Edit).",
        )
