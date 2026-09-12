from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "video-harness"
DEFAULT_BRIDGE_PORT = 8765
MARKER_SCHEMA = "video-harness.marker/v1"
LITE_BUNDLE_ID = "com.blackmagic-design.DaVinciResolveLite"


def lite_container_data() -> Path | None:
    """Mac App Store Resolve Lite sandbox Data folder, if it still exists on disk."""
    if not sys.platform.startswith("darwin"):
        return None
    path = Path.home() / "Library/Containers" / LITE_BUNDLE_ID / "Data"
    return path if path.is_dir() else None


def running_resolve_binary() -> Path | None:
    """Path of the live Resolve executable, if any."""
    try:
        import subprocess

        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    except Exception:
        return None
    for line in out.splitlines():
        cmd = line.strip()
        if "/Contents/MacOS/Resolve" not in cmd:
            continue
        if "python" in cmd.lower():
            continue
        # "  1234 /Applications/.../MacOS/Resolve"
        parts = cmd.split(None, 1)
        if len(parts) < 2:
            continue
        path = Path(parts[1].split()[0])
        if path.name == "Resolve":
            return path
    return None


def resolve_edition() -> str:
    """lite-mas vs desktop from the *running* app, not a leftover sandbox folder.

    Removing the App Store app leaves the container; 21.1 website install uses real $HOME.
    """
    proc = running_resolve_binary()
    if proc is not None:
        text = str(proc)
        if "/DaVinci Resolve/DaVinci Resolve.app/" in text:
            return "desktop"
        if text.startswith(str(Path("/Applications/DaVinci Resolve.app/"))):
            return "lite-mas"
        if "DaVinciResolveLite" in text:
            return "lite-mas"
        return "desktop"
    lite_app = Path("/Applications/DaVinci Resolve.app")
    desk_app = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
    lite_is_mas = False
    if lite_app.is_dir():
        receipt = lite_app / "Contents/_MASReceipt"
        plist = lite_app / "Contents/Info.plist"
        lite_is_mas = receipt.is_dir()
        if not lite_is_mas and plist.is_file():
            try:
                lite_is_mas = LITE_BUNDLE_ID in plist.read_text(errors="ignore")
            except OSError:
                pass
    if desk_app.is_dir() and not lite_is_mas:
        return "desktop"
    if lite_is_mas:
        return "lite-mas"
    return "desktop"


def config_dir() -> Path:
    override = os.environ.get("VIDEO_HARNESS_HOME")
    if override:
        return Path(override)
    # Lua inside Lite uses $HOME/.config/video-harness where HOME is the container.
    # Only follow that when Lite is actually the running (or only) app.
    if resolve_edition() == "lite-mas":
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
    if lite is not None and resolve_edition() == "lite-mas":
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
