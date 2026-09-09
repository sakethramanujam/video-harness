"""Resolve timeline clip colors (not marker colors)."""

from __future__ import annotations

from video_harness.errors import PlacementError

# TimelineItem.SetClipColor names. Marker-only names (Cyan, Mint, Red, …) are not valid.
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

# Names agents/users reach for because they are marker colors or CSS-ish.
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

_CLIP_BY_LOWER = {name.lower(): name for name in CLIP_COLORS}
_ALIAS_BY_LOWER = {name.lower(): target for name, target in CLIP_COLOR_ALIASES.items()}


def clip_color_help() -> str:
    aliases = ", ".join(f"{src}→{dst}" for src, dst in CLIP_COLOR_ALIASES.items())
    return f"Valid clip colors: {', '.join(CLIP_COLORS)}. Aliases: {aliases}."


def normalize_clip_color(color: str | None) -> str:
    """Return a Resolve clip color, or '' to clear. Raises PlacementError if unknown."""
    if color is None:
        return ""
    text = str(color).strip()
    if text == "":
        return ""
    key = text.lower()
    if key in _CLIP_BY_LOWER:
        return _CLIP_BY_LOWER[key]
    if key in _ALIAS_BY_LOWER:
        return _ALIAS_BY_LOWER[key]
    raise PlacementError(
        f"Invalid clip color '{color}'. {clip_color_help()}",
        state={"color": color, "valid": list(CLIP_COLORS)},
    )
