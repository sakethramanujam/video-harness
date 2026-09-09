from __future__ import annotations

import os
from typing import Any, Literal

from video_harness.bridge_client import BridgeClient, FileBridgeClient
from video_harness.direct import call_direct, connect_direct
from video_harness.errors import ConnectionError, HarnessError

Transport = Literal["direct", "bridge", "lua"]


class Session:
    def __init__(self, transport: Transport, impl: Any) -> None:
        self.transport = transport
        self._impl = impl

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if self.transport == "direct":
            result = call_direct(self._impl, method, params)
            if not result.get("ok"):
                err = result.get("error") or {}
                raise HarnessError(
                    err.get("message") or "Resolve call failed.",
                    type=err.get("type") or "HarnessError",
                    cause=err.get("cause"),
                    fix=err.get("fix"),
                    state=err.get("state") or {},
                )
            return result.get("result")
        return self._impl.call(method, params)

    def ping(self) -> dict[str, Any]:
        result = self.call("ping")
        result["transport"] = self.transport
        return result


def connect(transport: str | None = None) -> Session:
    choice = (transport or os.environ.get("VIDEO_HARNESS_TRANSPORT") or "auto").lower()
    errors: list[str] = []
    if choice in ("auto", "direct"):
        try:
            resolve = connect_direct()
            return Session("direct", resolve)
        except Exception as exc:
            errors.append(f"direct: {exc}")
            if choice == "direct":
                raise
    if choice in ("auto", "bridge"):
        try:
            client = BridgeClient.from_config()
            client.health()
            return Session("bridge", client)
        except Exception as exc:
            errors.append(f"bridge: {exc}")
            if choice == "bridge":
                raise
    if choice in ("auto", "lua", "bridge"):
        try:
            client = FileBridgeClient.from_config()
            client.health()
            return Session("lua", client)
        except Exception as exc:
            errors.append(f"lua: {exc}")
            if choice == "lua":
                raise
    raise ConnectionError(
        "Could not reach DaVinci Resolve.",
        cause=" | ".join(errors) or "no transports tried",
        fix=(
            "Free: Workspace > Scripts > Utility > video_harness_bridge (Lua) and leave it running. "
            "Python scripts stay hidden until Resolve finds Python; Lua always lists."
        ),
        state={"tried": errors, "transport": choice},
    )
