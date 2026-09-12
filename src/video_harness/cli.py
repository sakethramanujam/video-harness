from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from video_harness import __version__
from video_harness.errors import HarnessError
from video_harness.paths import (
    DEFAULT_BRIDGE_PORT,
    bridge_config_path,
    config_dir,
    fusionscript_candidates,
    resolve_script_dirs,
    scripting_module_dirs,
)
from video_harness.registry import TypeRegistry


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_doctor(_: argparse.Namespace) -> int:
    from video_harness.direct import scriptapp_resolve

    process = _resolve_running()
    libs = [str(p) for p in fusionscript_candidates() if p.is_file()]
    modules = [str(p) for p in scripting_module_dirs() if p.is_dir()]
    cfg_path = bridge_config_path()
    script_path = resolve_script_dirs()["user"] / "video_harness_bridge.py"
    py = _scripts_python_status()
    from video_harness.paths import lite_container_data, resolve_edition, resolve_script_roots

    report: dict[str, Any] = {
        "video_harness": __version__,
        "resolve_edition": resolve_edition(),
        "script_roots": [str(p) for p in resolve_script_roots() if p.is_dir()],
        "python": sys.version.split()[0],
        "python3home": py["python3home"],
        "usr_local_python3": py["usr_local_python3"],
        "scripts_python": py,
        "resolve_process": process,
        "fusionscript": libs,
        "scripting_modules": modules,
        "bridge_script": str(script_path) if script_path.is_file() else None,
        "lite_container": str(lite_container_data()) if lite_container_data() else None,
        "bridge_config": str(cfg_path) if cfg_path.is_file() else None,
        "scriptapp": None,
        "bridge": None,
        "next": [],
    }
    try:
        resolve = scriptapp_resolve()
        if resolve:
            report["scriptapp"] = {
                "connected": True,
                "product": resolve.GetProductName(),
                "version": resolve.GetVersionString(),
                "page": resolve.GetCurrentPage(),
            }
        else:
            report["scriptapp"] = {
                "connected": False,
                "note": "None — typical on free Resolve. Use the in-app bridge.",
            }
    except Exception as exc:
        report["scriptapp"] = {"connected": False, "error": str(exc)}

    if cfg_path.is_file() or (config_dir() / "bridge-heartbeat.json").is_file():
        from video_harness.bridge_client import BridgeClient, FileBridgeClient

        http_err = None
        lua_err = None
        if cfg_path.is_file():
            try:
                report["bridge"] = BridgeClient.from_config().health()
            except Exception as exc:
                http_err = str(exc)
        if not (report.get("bridge") or {}).get("ok"):
            try:
                report["bridge"] = FileBridgeClient.from_config().health()
            except Exception as exc:
                lua_err = str(exc)
                report["bridge"] = {
                    "ok": False,
                    "http": http_err,
                    "lua": lua_err,
                }

    report["next"] = _doctor_next(report)
    _print(report)
    return 0


def _scripts_python_status() -> dict[str, Any]:
    local = Path("/usr/local/bin/python3")
    home = os.environ.get("PYTHON3HOME") or _launchctl_python3home()
    home_python3 = Path(home) / "bin" / "python3" if home else None
    visible = bool(local.exists() or (home_python3 and home_python3.exists()))
    note = None
    if not visible:
        note = (
            "Resolve on macOS will not list .py scripts. It execs "
            "$PYTHON3HOME/bin/python3 or /usr/local/bin/python3 "
            "(Homebrew PATH and a versioned python3.12 name are ignored). "
            "Run: video-harness enable-python"
        )
    elif home and home_python3 and not home_python3.exists():
        note = (
            f"PYTHON3HOME is {home} but bin/python3 is missing "
            f"(Homebrew only ships python3.12). Run: video-harness enable-python"
        )
        visible = False
    return {
        "ok": visible,
        "python3home": home,
        "python3home_python3": str(home_python3) if home_python3 and home_python3.exists() else None,
        "usr_local_python3": str(local) if local.exists() else None,
        "note": note,
    }


def _doctor_next(report: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    bridge = report.get("bridge") or {}
    lua = str(bridge.get("lua") or "")
    if "methods" in lua.lower() or "older than this cli" in lua.lower():
        steps.append(
            "Running Lua is older than this CLI. Re-click Workspace > Scripts > Utility > video_harness_bridge (one instance)."
        )
    if bridge.get("ok"):
        return ["Bridge is up. video-harness inspect"]
    if not report.get("bridge_script"):
        steps.append("video-harness install-bridge")
    scripts_py = report.get("scripts_python") or {}
    if not scripts_py.get("ok"):
        steps.append("video-harness enable-python")
        steps.append("Quit DaVinci Resolve completely (Cmd+Q), then reopen it.")
    elif report.get("resolve_process", {}).get("running"):
        steps.append(
            "If you just set PYTHON3HOME, quit Resolve completely (Cmd+Q) and reopen so it inherits it."
        )
    if not report.get("resolve_process", {}).get("running"):
        steps.append("Open DaVinci Resolve and a project.")
    steps.append(
        "Workspace > Scripts > Utility > video_harness_bridge  (Lua — Python .py files stay hidden until Resolve finds Python)."
    )
    steps.append("video-harness doctor   # bridge.ok should become true")
    return steps


PREFERRED_PYTHONS = (
    "python3.12",
    "python3.11",
    "python3.10",
    "python3.13",
    "python3.9",
)


def _resolve_python() -> tuple[Path, str]:
    for name in PREFERRED_PYTHONS:
        exe = shutil.which(name)
        if not exe:
            brew = Path("/opt/homebrew/bin") / name
            exe = str(brew) if brew.is_file() else None
        if not exe:
            continue
        prefix = subprocess.check_output(
            [exe, "-c", "import sys; print(sys.prefix)"], text=True
        ).strip()
        return Path(exe), prefix
    prefix = subprocess.check_output(
        [sys.executable, "-c", "import sys; print(sys.prefix)"], text=True
    ).strip()
    return Path(sys.executable), prefix


def cmd_enable_python(_: argparse.Namespace) -> int:
    """Make Workspace > Scripts see a Python 3 interpreter (macOS)."""
    exe, prefix = _resolve_python()
    launchctl_set = False
    try:
        subprocess.run(["launchctl", "setenv", "PYTHON3HOME", prefix], check=False)
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "asuser", str(uid), "launchctl", "setenv", "PYTHON3HOME", prefix],
            check=False,
        )
        launchctl_set = True
    except Exception:
        pass

    agent = Path.home() / "Library/LaunchAgents/com.video-harness.python3home.plist"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.video-harness.python3home</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/launchctl</string>
    <string>setenv</string>
    <string>PYTHON3HOME</string>
    <string>%s</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
"""
        % prefix
    )
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(agent)], check=False, capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(agent)], check=False, capture_output=True)

    # Resolve execs $PYTHON3HOME/bin/python3 (unversioned). Homebrew only ships python3.12.
    home_bin = Path(prefix) / "bin"
    unversioned = home_bin / "python3"
    if home_bin.is_dir() and not unversioned.exists():
        target = home_bin / exe.name
        if target.exists():
            unversioned.symlink_to(target.name)
        elif exe.exists():
            unversioned.symlink_to(exe)

    local = Path("/usr/local/bin/python3")
    symlink_ok = local.exists()
    sudo_cmd = f"sudo ln -sf {exe} /usr/local/bin/python3"
    if not symlink_ok:
        try:
            local.parent.mkdir(parents=True, exist_ok=True)
            if local.exists() or local.is_symlink():
                local.unlink()
            local.symlink_to(exe)
            symlink_ok = local.exists()
        except OSError:
            symlink_ok = False

    _print(
        {
            "python": str(exe),
            "PYTHON3HOME": prefix,
            "launchctl": launchctl_set,
            "launch_agent": str(agent),
            "usr_local_python3": str(local) if local.exists() else None,
            "sudo_symlink": None if symlink_ok else sudo_cmd,
            "next": [
                "If sudo_symlink is set, run that one command (Resolve hardcodes /usr/local/bin/python3).",
                "Quit DaVinci Resolve completely (Cmd+Q) — a page switch is not enough.",
                "Reopen Resolve, open a project.",
                "Workspace > Scripts > Utility > video_harness_bridge",
                "video-harness doctor",
            ],
        }
    )
    return 0


def _resolve_running() -> dict[str, Any]:
    try:
        out = subprocess.check_output(["pgrep", "-lf", "Resolve"], text=True)
    except subprocess.CalledProcessError:
        return {"running": False, "matches": []}
    except Exception as exc:
        return {"running": None, "error": str(exc)}
    lines = [
        ln
        for ln in out.splitlines()
        if "Resolve" in ln and "pgrep" not in ln
    ]
    return {"running": bool(lines), "matches": lines[:8]}


def _launchctl_python3home() -> str | None:
    try:
        out = subprocess.check_output(["launchctl", "getenv", "PYTHON3HOME"], text=True).strip()
        return out or None
    except Exception:
        return None


def cmd_install_bridge(args: argparse.Namespace) -> int:
    dest = resolve_script_dirs()["user"]
    dest.mkdir(parents=True, exist_ok=True)
    pkg_scripts = Path(__file__).resolve().parent / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pkg_scripts / "vh_runtime.py", dest / "vh_runtime.py")
    shutil.copy2(pkg_scripts / "bridge.py", dest / "video_harness_bridge.py")
    lua_src = pkg_scripts / "video_harness_bridge.lua"
    copied_lua = []
    from video_harness.paths import lite_container_data, resolve_script_roots

    removed_lua: list[str] = []
    if lua_src.is_file():
        for scripts_root in resolve_script_roots():
            utility = scripts_root / "Utility"
            try:
                utility.mkdir(parents=True, exist_ok=True)
                target = utility / "video_harness_bridge.lua"
                shutil.copy2(lua_src, target)
                copied_lua.append(str(target))
            except OSError:
                pass
            # Older installs copied into Edit/Comp and hijacked those Scripts menus.
            for folder in ("Edit", "Comp", "Color", "Fairlight", "Deliver"):
                stray = scripts_root / folder / "video_harness_bridge.lua"
                if stray.is_file():
                    try:
                        stray.unlink()
                        removed_lua.append(str(stray))
                    except OSError:
                        continue

    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "rpc").mkdir(parents=True, exist_ok=True)
    cfg_path = bridge_config_path()
    token = secrets.token_urlsafe(24)
    port = int(args.port or DEFAULT_BRIDGE_PORT)
    if cfg_path.is_file() and not args.rotate_token:
        existing = json.loads(cfg_path.read_text())
        token = existing.get("token") or token
        port = int(existing.get("port") or port)
    cfg = {"host": "127.0.0.1", "port": port, "token": token, "version": 1}
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")

    python_note = None
    if sys.platform == "darwin":
        local_py = Path("/usr/local/bin/python3")
        if not local_py.exists():
            python_note = (
                "Resolve on macOS ignores Homebrew PATH. Run `video-harness enable-python`, "
                "then quit and reopen Resolve so Workspace > Scripts lists .py files."
            )

    _print(
        {
            "installed": [
                str(dest / "video_harness_bridge.py"),
                str(dest / "vh_runtime.py"),
                *copied_lua,
            ],
            "removed": removed_lua,
            "config": str(cfg_path),
            "port": port,
            "next": [
                "If the Lua bridge is already running, click it again (one instance) so it loads this copy.",
                "Do not launch fuscript from a terminal on App Store Lite — Resolve will crash it.",
                "Workspace > Scripts > Utility > video_harness_bridge  (Lua; always listed).",
                "Leave it running, then: video-harness doctor",
            ],
            "python_note": python_note,
        }
    )
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    from video_harness.harness import Harness
    from video_harness.session import connect

    harness = Harness(connect(args.transport))
    _print(harness.inspect(media=args.media))
    return 0


def cmd_types(_: argparse.Namespace) -> int:
    _print(TypeRegistry.load().to_dict())
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from video_harness.mcp_server import main as mcp_main

    mcp_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video-harness",
        description="DaVinci Resolve harness for timeline placement and typed markers.",
    )
    parser.add_argument("--version", action="version", version=f"video-harness {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    doctor = sub.add_parser("doctor", help="Diagnose Resolve, fusionscript, and the in-app bridge.")
    doctor.set_defaults(func=cmd_doctor)

    enable_py = sub.add_parser(
        "enable-python",
        help="Point Resolve at a Python 3 interpreter so Workspace > Scripts lists .py files (macOS).",
    )
    enable_py.set_defaults(func=cmd_enable_python)

    install = sub.add_parser(
        "install-bridge",
        help="Install the Workspace > Scripts bridge (needed on free Resolve).",
    )
    install.add_argument("--port", type=int, default=DEFAULT_BRIDGE_PORT)
    install.add_argument("--rotate-token", action="store_true")
    install.set_defaults(func=cmd_install_bridge)

    inspect = sub.add_parser("inspect", help="Dump current project / timeline / markers.")
    inspect.add_argument("--transport", choices=("auto", "direct", "bridge", "lua"), default="auto")
    inspect.add_argument("--media", choices=("current", "all"), default="current")
    inspect.set_defaults(func=cmd_inspect)

    types_cmd = sub.add_parser("types", help="Show the marker type registry.")
    types_cmd.set_defaults(func=cmd_types)

    mcp = sub.add_parser("mcp", help="Run the MCP server on stdio.")
    mcp.set_defaults(func=cmd_mcp)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except HarnessError as exc:
        _print({"error": exc.to_dict()})
        raise SystemExit(2) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
