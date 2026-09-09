from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Any

from video_harness.errors import ConnectionError
from video_harness.paths import fusionscript_candidates, scripting_module_dirs
from video_harness.scripts import vh_runtime


def _local_hosts() -> list[str]:
    hosts = ["127.0.0.1", "localhost"]
    try:
        hostname = socket.gethostname()
        hosts.append(hostname)
        hosts.extend(socket.gethostbyname_ex(hostname)[2])
    except Exception:
        pass
    try:
        import subprocess
        import re

        out = subprocess.check_output(["ifconfig"], text=True, stderr=subprocess.DEVNULL)
        hosts.extend(re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", out))
    except Exception:
        pass
    seen: list[str] = []
    for host in hosts:
        if host and host not in seen and not host.startswith("127.0.0."):
            seen.append(host)
        elif host in ("127.0.0.1", "localhost") and host not in seen:
            seen.append(host)
    # Prefer loopback first, then LAN (macOS Studio quirk).
    ordered = [h for h in ("127.0.0.1", "localhost") if h in seen]
    ordered.extend(h for h in seen if h not in ordered)
    return ordered


def bootstrap_fusionscript() -> Any:
    env_lib = os.environ.get("RESOLVE_SCRIPT_LIB")
    libs = [Path(env_lib)] if env_lib else []
    libs.extend(fusionscript_candidates())
    for lib in libs:
        if lib.is_file():
            os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(lib))
            break
    for directory in scripting_module_dirs():
        if directory.is_dir() and str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    try:
        import DaVinciResolveScript as dvr  # type: ignore
    except Exception as exc:
        raise ConnectionError(
            "Could not import DaVinciResolveScript / fusionscript.",
            cause=str(exc),
            fix="Install DaVinci Resolve. On this Mac the module lives inside the .app bundle.",
        ) from exc
    return dvr


def scriptapp_resolve() -> Any:
    dvr = bootstrap_fusionscript()
    resolve = dvr.scriptapp("Resolve")
    if resolve:
        return resolve
    for host in _local_hosts():
        try:
            resolve = dvr.scriptapp("Resolve", host)
        except TypeError:
            break
        except Exception:
            continue
        if resolve:
            return resolve
    return None


def connect_direct() -> Any:
    resolve = scriptapp_resolve()
    if not resolve:
        raise ConnectionError(
            "scriptapp('Resolve') returned None.",
            cause="External scripting is Studio-only (gated since ~19.1), or it is set to None in Preferences.",
            fix=(
                "Studio: Preferences > General > External scripting using = Local, then retry. "
                "Free: video-harness install-bridge, restart Resolve, Workspace > Scripts > video_harness_bridge."
            ),
        )
    return resolve


def call_direct(resolve: Any, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return vh_runtime.dispatch(resolve, method, params or {})
