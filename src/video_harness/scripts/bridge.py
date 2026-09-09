#!/usr/bin/env python
"""In-app HTTP bridge. Launch from Workspace > Scripts > video_harness_bridge."""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    import vh_runtime
except ImportError:
    vh_runtime = None

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
BRIDGE_VERSION = "0.1.0"


def _config_path():
    override = os.environ.get("VIDEO_HARNESS_BRIDGE_CONFIG")
    if override:
        return override
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        root = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return os.path.join(root, "video-harness", "bridge.json")
    return os.path.join(home, ".config", "video-harness", "bridge.json")


def load_config():
    path = _config_path()
    data = {"host": HOST, "port": DEFAULT_PORT, "token": ""}
    try:
        with open(path, "r") as handle:
            loaded = json.load(handle)
            if isinstance(loaded, dict):
                data.update(loaded)
    except Exception:
        pass
    return data, path


def get_resolve():
    for attempt in (
        lambda: fu.GetResolve(),  # noqa: F821
        lambda: fusion.GetResolve(),  # noqa: F821
        lambda: bmd.scriptapp("Resolve"),  # noqa: F821
    ):
        try:
            obj = attempt()
            if obj:
                return obj
        except Exception:
            pass
    try:
        import DaVinciResolveScript as dvr

        return dvr.scriptapp("Resolve")
    except Exception:
        return None


def make_handler(resolve, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("[video-harness-bridge] " + (fmt % args) + "\n")

        def _send(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] in ("/health", "/"):
                product = None
                version = None
                try:
                    product = resolve.GetProductName() if resolve else None
                    version = resolve.GetVersionString() if resolve else None
                except Exception:
                    pass
                self._send(
                    200,
                    {
                        "ok": bool(resolve),
                        "bridge": BRIDGE_VERSION,
                        "product": product,
                        "version": version,
                    },
                )
                return
            self._send(404, {"ok": False, "error": {"type": "NotFound", "message": "GET /health"}})

        def do_POST(self):
            if self.path.split("?")[0] not in ("/rpc", "/"):
                self._send(404, {"ok": False, "error": {"type": "NotFound", "message": "POST /rpc"}})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                request = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                self._send(400, {"ok": False, "error": {"type": "BadRequest", "message": "Invalid JSON"}})
                return
            req_token = request.get("token") or self.headers.get("X-Video-Harness-Token")
            if token and req_token != token:
                self._send(
                    401,
                    {
                        "ok": False,
                        "id": request.get("id"),
                        "error": {
                            "type": "AuthError",
                            "message": "Bad or missing bridge token.",
                            "fix": "Run video-harness install-bridge and use ~/.config/video-harness/bridge.json.",
                        },
                    },
                )
                return
            if not resolve:
                self._send(
                    503,
                    {
                        "ok": False,
                        "id": request.get("id"),
                        "error": {
                            "type": "ConnectionError",
                            "message": "Bridge has no Resolve object.",
                            "fix": "Launch this script from Workspace > Scripts inside a project.",
                        },
                    },
                )
                return
            if vh_runtime is None:
                self._send(
                    500,
                    {
                        "ok": False,
                        "id": request.get("id"),
                        "error": {
                            "type": "BridgeError",
                            "message": "vh_runtime.py is not next to the bridge script.",
                            "fix": "Re-run video-harness install-bridge.",
                        },
                    },
                )
                return
            method = request.get("method")
            params = request.get("params") or {}
            try:
                result = vh_runtime.dispatch(resolve, method, params)
            except Exception as exc:
                result = {
                    "ok": False,
                    "error": {
                        "type": "BridgeError",
                        "message": str(exc),
                        "cause": traceback.format_exc(),
                    },
                }
            result["id"] = request.get("id")
            self._send(200 if result.get("ok") else 400, result)

    return Handler


def serve(resolve=None, host=None, port=None, token=None):
    cfg, path = load_config()
    host = host or cfg.get("host") or HOST
    port = int(port or cfg.get("port") or DEFAULT_PORT)
    token = token if token is not None else cfg.get("token") or ""
    resolve = resolve or get_resolve()
    if resolve:
        try:
            print(
                "[video-harness-bridge] Connected to %s %s"
                % (resolve.GetProductName(), resolve.GetVersionString())
            )
        except Exception:
            print("[video-harness-bridge] Connected (could not read product name).")
    else:
        print("[video-harness-bridge] WARNING: no Resolve object. Health will report disconnected.")
    print("[video-harness-bridge] Listening on http://%s:%s  config=%s" % (host, port, path))
    print("[video-harness-bridge] Leave this script running. Stop it from the Scripts console to quit.")
    server = HTTPServer((host, int(port)), make_handler(resolve, token))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[video-harness-bridge] stopped")


if __name__ == "__main__":
    serve()
