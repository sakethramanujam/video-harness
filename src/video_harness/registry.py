from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from video_harness.errors import UnknownTypeError
from video_harness.paths import types_path

Scope = Literal["timeline", "item", "clip"]
DurationKind = Literal["point", "range"]

VALID_COLORS = (
    "Blue",
    "Cyan",
    "Green",
    "Yellow",
    "Red",
    "Pink",
    "Purple",
    "Fuchsia",
    "Rose",
    "Lavender",
    "Sky",
    "Mint",
    "Lemon",
    "Sand",
    "Cocoa",
    "Cream",
    "White",
    "Black",
    "Orange",
    "Brown",
    "Gray",
    "Light Gray",
    "Magenta",
)


@dataclass(frozen=True)
class MarkerType:
    id: str
    color: str
    scope: Scope
    duration: DurationKind
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "color": self.color,
            "scope": self.scope,
            "duration": self.duration,
            "description": self.description,
        }


class TypeRegistry:
    def __init__(self, types: dict[str, MarkerType], *, source: Path | None = None) -> None:
        self.types = types
        self.source = source

    @classmethod
    def load(cls, path: Path | None = None) -> TypeRegistry:
        path = path or types_path()
        raw = yaml.safe_load(path.read_text()) or {}
        items: dict[str, MarkerType] = {}
        for type_id, spec in (raw.get("types") or {}).items():
            items[type_id] = MarkerType(
                id=type_id,
                color=spec.get("color", "Blue"),
                scope=spec.get("scope", "timeline"),
                duration=spec.get("duration", "point"),
                description=spec.get("description", ""),
            )
        return cls(items, source=path)

    def get(self, type_id: str) -> MarkerType:
        if type_id not in self.types:
            raise UnknownTypeError(type_id)
        return self.types[type_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source) if self.source else None,
            "types": [t.to_dict() for t in self.types.values()],
        }
