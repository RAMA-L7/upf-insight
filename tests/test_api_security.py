"""API server security tests - path-traversal (LFI) guard on the workspace server."""

import json
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request

import pytest

from upf_insight.api import api_server

WEB = api_server._WEB_DIR
ROOT = api_server._WORKSPACE_ROOT


@pytest.fixture()
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), api_server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _get(base, path):
    try:
        with urlopen(base + path, timeout=5) as r:
            return r.status, r.read()
    except Exception as e:  # HTTPError for 4xx/5xx
        return e.code, b""


def test_assets_direct_traversal_is_rejected(server):
    status, _ = _get(server, "/assets/../../../Windows/win.ini")
    assert status == 403


def test_assets_encoded_traversal_is_rejected(server):
    status, _ = _get(server, "/assets/%2e%2e/%2e%2e/secret.txt")
    assert status in (403, 404)


def test_assets_in_root_serves_200(server):
    status, _ = _get(server, "/assets/css/app.css")
    assert status == 200


def test_validate_out_of_root_file_returns_400(server):
    body = json.dumps({"files": [r"C:\Windows\win.ini"]}).encode()
    req = Request(server + "/api/validate", data=body,
                  headers={"Content-Type": "application/json"})
    with pytest.raises(Exception) as ei:
        urlopen(req, timeout=5)
    status = ei.value.code
    assert status == 400
    err = json.loads(ei.value.read())
    assert "workspace root" in err["error"]


def test_validate_netlist_out_of_root_returns_400(server):
    body = json.dumps({"files": [], "netlist": "/etc/passwd"}).encode()
    req = Request(server + "/api/validate", data=body,
                  headers={"Content-Type": "application/json"})
    with pytest.raises(Exception) as ei:
        urlopen(req, timeout=5)
    assert ei.value.code == 400


def test_validate_in_root_file_is_allowed(server):
    golden = os.path.join("tests", "examples", "example.soc.upf")
    body = json.dumps({"files": [golden]}).encode()
    req = Request(server + "/api/validate", data=body,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=10) as r:
        assert r.status == 200
        result = json.loads(r.read())
    assert result["command_count"] >= 20
    assert result["check"]["clean"] is True


def test_validate_content_ignores_files(server):
    body = json.dumps({"content": "upf_version 3.0\n"}).encode()
    req = Request(server + "/api/validate", data=body,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=10) as r:
        assert r.status == 200

# ── Request-body bounds ─────────────────────────────────────────────────────
#
# A malformed body must come back as a readable 4xx, not a dropped
# connection, and an oversized one must be refused before it is read.

def _post(base, body, path="/api/validate", extra_headers=None):
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = Request(base + path, data=body, headers=headers)
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except Exception as e:  # HTTPError for 4xx
        return getattr(e, "code", None), b""


def test_valid_body_still_returns_200(server):
    status, _ = _post(server, json.dumps({"content": "create_power_domain PD_A"}).encode())
    assert status == 200


def test_malformed_json_returns_400_not_a_dropped_connection(server):
    status, _ = _post(server, b"not json at all")
    assert status == 400


def test_non_object_json_returns_400(server):
    status, _ = _post(server, b"[1, 2, 3]")
    assert status == 400


def test_empty_body_is_accepted(server):
    status, _ = _post(server, b"")
    assert status == 200


def test_oversized_body_is_refused_with_413(server):
    oversized = str(api_server._MAX_BODY_BYTES + 1)
    status, _ = _post(server, b"{}", extra_headers={"Content-Length": oversized})
    assert status == 413


def test_negative_content_length_returns_400(server):
    status, _ = _post(server, b"{}", extra_headers={"Content-Length": "-5"})
    assert status == 400
