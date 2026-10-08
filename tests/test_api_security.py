"""API server security tests - path-traversal (LFI) guard on the workspace server."""

import json
import os
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
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


@pytest.fixture()
def outside_root_file():
    """An existing file guaranteed to sit outside the workspace root.

    A hardcoded Windows path only exercises the root bound *on Windows*; on
    POSIX ``C:\\Windows\\win.ini`` is a relative name that resolves inside the
    root, so the request reached the engine with a missing file and the server
    dropped the connection. A temp file keeps the test about the root bound on
    every platform.
    """
    fd, path = tempfile.mkstemp(prefix="upf-outside-root-", suffix=".upf")
    os.close(fd)
    assert not os.path.realpath(path).startswith(os.path.realpath(ROOT) + os.sep), \
        "temp file unexpectedly inside the workspace root"
    yield path
    os.remove(path)


def test_validate_out_of_root_file_returns_400(server, outside_root_file):
    body = json.dumps({"files": [outside_root_file]}).encode()
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
    except HTTPError as e:
        # Only a real HTTP status counts. A transport failure must surface as
        # itself, not collapse to None -- masking it here is what made these
        # assertions intermittently fail for the wrong reason.
        return e.code, e.read()
    except Exception as e:  # URLError, RemoteDisconnected, timeouts
        return type(e).__name__, b""


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


def test_validate_missing_in_root_file_returns_400_not_a_dropped_connection(server):
    """A path inside the root that does not exist must be a readable 400.

    On POSIX the old assertion passed a Windows path that resolved *inside*
    the root, so the engine raised FileNotFoundError and the client saw a
    dropped connection instead of a status.
    """
    missing = os.path.join("tests", "examples", "no_such_file.upf")
    status, body = _post(server, json.dumps({"files": [missing]}).encode())
    assert status == 400
    assert "not found" in json.loads(body)["error"]


def test_negative_content_length_returns_400(server):
    status, _ = _post(server, b"{}", extra_headers={"Content-Length": "-5"})
    assert status == 400
