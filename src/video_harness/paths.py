from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "video-harness"
DEFAULT_BRIDGE_PORT = 8765
MARKER_SCHEMA = "video-harness.marker/v1"
LITE_BUNDLE_ID = "com.blackmagic-design.DaVinciResolveLite"


def lite_container_data() -> Path | None:
    """Mac App Store Resolve Lite is sandboxed; its HOME is this Data folder."""
    if not sys.platform.startswith("darwin"):
        return None
    path = Path.home() / "Library/Containers" / LITE_BUNDLE_ID / "Data"
    return path if path.is_dir() else None


def config_dir() -> Path:
    override = os.environ.get("VIDEO_HARNESS_HOME")
    if override:
        return Path(override)
    # Lua inside Lite uses $HOME/.config/video-harness where HOME is the container.
    lite = lite_container_data()
    if lite is not None:
        return lite / ".config" / APP_NAME
    if sys.platform.startswith("win"):
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / APP_NAME
    return Path.home() / ".config" / APP_NAME


def bridge_config_path() -> Path:
    override = os.environ.get("VIDEO_HARNESS_BRIDGE_CONFIG")
    if override:
        return Path(override)
    return config_dir() / "bridge.json"


def types_path() -> Path:
    override = os.environ.get("VIDEO_HARNESS_TYPES")
    if override:
        return Path(override)
    return Path(__file__).with_name("types.yaml")


def resolve_script_roots() -> list[Path]:
    """Every Fusion/Scripts tree this install might actually scan."""
    home = Path.home()
    roots: list[Path] = []
    lite = lite_container_data()
    if lite is not None:
        roots.append(lite / "Library/Application Support/Fusion/Scripts")
    if sys.platform.startswith("darwin"):
        roots.append(
            home
            / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"
        )
        roots.append(
            Path(
                "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"
            )
        )
        return roots
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        programdata = os.environ.get("PROGRAMDATA") or "C:\\ProgramData"
        roots.extend(
            [
                Path(appdata) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts",
                Path(programdata) / "Blackmagic Design/DaVinci Resolve/Fusion/Scripts",
            ]
        )
        return roots
    roots.extend(
        [
            home / ".local/share/DaVinciResolve/Fusion/Scripts",
            Path("/opt/resolve/Fusion/Scripts"),
        ]
    )
    return roots


def resolve_script_dirs() -> dict[str, Path]:
    roots = resolve_script_roots()
    home = Path.home()
    user = roots[0] / "Utility" if roots else home / "Fusion/Scripts/Utility"
    if sys.platform.startswith("darwin"):
        return {
            "user": user,
            "all": Path(
                "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
            ),
        }
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        programdata = os.environ.get("PROGRAMDATA") or "C:\\ProgramData"
        return {
            "user": Path(appdata)
            / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Utility",
            "all": Path(programdata)
            / "Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility",
        }
    return {
        "user": home / ".local/share/DaVinciResolve/Fusion/Scripts/Utility",
        "all": Path("/opt/resolve/Fusion/Scripts/Utility"),
    }


def fusionscript_candidates() -> list[Path]:
    if sys.platform.startswith("darwin"):
        return [
            Path("/Applications/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"),
            Path(
                "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
            ),
        ]
    if sys.platform.startswith("win"):
        return [
            Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll"),
        ]
    return [
        Path("/opt/resolve/libs/Fusion/fusionscript.so"),
        Path("/home/resolve/libs/Fusion/fusionscript.so"),
    ]


def scripting_module_dirs() -> list[Path]:
    if sys.platform.startswith("darwin"):
        return [
            Path(
                "/Applications/DaVinci Resolve.app/Contents/Resources/Developer/Scripting/Modules"
            ),
            Path(
                "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
            ),
            Path.home()
            / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
        ]
    if sys.platform.startswith("win"):
        programdata = os.environ.get("PROGRAMDATA") or "C:\\ProgramData"
        return [
            Path(programdata)
            / "Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules",
        ]
    return [
        Path("/opt/resolve/Developer/Scripting/Modules"),
        Path("/home/resolve/Developer/Scripting/Modules"),
    ]
