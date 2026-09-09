import json
from http.client import HTTPConnection
from http.server import HTTPServer
from threading import Thread

from tests.fakes import FakeResolve
from video_harness.scripts.bridge import make_handler


def test_rpc_roundtrip():
    resolve = FakeResolve()
    handler = make_handler(resolve, token="secret")
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/health")
        health = json.loads(conn.getresponse().read())
        assert health["ok"] is True

        body = json.dumps({"id": 7, "token": "secret", "method": "ping", "params": {}})
        conn.request("POST", "/rpc", body=body, headers={"Content-Type": "application/json"})
        payload = json.loads(conn.getresponse().read())
        assert payload["ok"] is True
        assert payload["id"] == 7
        assert payload["result"]["product"] == "DaVinci Resolve"

        conn.request(
            "POST",
            "/rpc",
            body=json.dumps({"token": "nope", "method": "ping"}),
            headers={"Content-Type": "application/json"},
        )
        denied = json.loads(conn.getresponse().read())
        assert denied["ok"] is False
        assert denied["error"]["type"] == "AuthError"
    finally:
        server.shutdown()
        server.server_close()
