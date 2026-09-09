from __future__ import annotations

from typing import Any


class HarnessError(Exception):
    def __init__(
        self,
        message: str,
        *,
        type: str = "HarnessError",
        cause: str | None = None,
        fix: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.type = type
        self.message = message
        self.cause = cause
        self.fix = fix
        self.state = state or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "message": self.message,
            "state": self.state,
        }
        if self.cause:
            payload["cause"] = self.cause
        if self.fix:
            payload["fix"] = self.fix
        return payload


class ConnectionError(HarnessError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, type="ConnectionError", **kwargs)


class NoProjectError(HarnessError):
    def __init__(self, message: str = "No project is open.", **kwargs: Any) -> None:
        kwargs.setdefault("fix", "Open a project in DaVinci Resolve, then retry.")
        super().__init__(message, type="NoProjectError", **kwargs)


class NoTimelineError(HarnessError):
    def __init__(self, message: str = "No timeline is current.", **kwargs: Any) -> None:
        kwargs.setdefault("fix", "Create or switch to a timeline first.")
        super().__init__(message, type="NoTimelineError", **kwargs)


class PlacementError(HarnessError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, type="PlacementError", **kwargs)


class MarkerError(HarnessError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, type="MarkerError", **kwargs)


class UnknownTypeError(HarnessError):
    def __init__(self, type_id: str, **kwargs: Any) -> None:
        super().__init__(
            f"Unknown marker type '{type_id}'.",
            type="UnknownTypeError",
            fix="Check type_registry_get / types.yaml.",
            state={"type": type_id, **(kwargs.get("state") or {})},
            **{k: v for k, v in kwargs.items() if k != "state"},
        )
