"""Web API regression tests for the analysis workflow endpoints.

Covers /api/diff, /api/gate, /api/report and /api/sample - each must return
REAL engine evidence (never fake results) and honest error states.
"""

import json
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import pytest

from upf_insight.api import api_server

FIX = os.path.join("tests", "examples", "cpu_subsys")


@pytest.fixture()
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), api_server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _post(base, path, payload):
    req = Request(base + path, data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, json.loads(e.read())


def _get(base, path):
    try:
        with urlopen(base + path, timeout=10) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, None


def _read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


V1 = _read("cpu_subsys_v1.upf")
V2 = _read("cpu_subsys_v2.upf")


# ── /api/diff ────────────────────────────────────────────────────────────────

def test_diff_identifies_regression(server):
    status, d = _post(server, "/api/diff", {"old": V1, "new": V2})
    assert status == 200
    assert any(c["what"] == "strategy" and "level_shifter" in c["name"] + c["detail"]
               for c in d["changes"])


def test_diff_identical_versions_no_changes(server):
    status, d = _post(server, "/api/diff", {"old": V1, "new": V1})
    assert status == 200
    assert d["changes"] == []


def test_diff_missing_input_400(server):
    status, err = _post(server, "/api/diff", {"old": V1})
    assert status == 400
    assert "both" in err["error"]


# ── /api/gate ────────────────────────────────────────────────────────────────

def test_gate_v1_passes_strict(server):
    status, g = _post(server, "/api/gate", {"content": V1, "policy": "STRICT"})
    assert status == 200
    assert g["gate"]["passed"] is True
    assert g["gate"]["exit_code"] == 0


def test_gate_v2_fails_strict_with_reasons(server):
    status, g = _post(server, "/api/gate", {"content": V2, "policy": "STRICT"})
    assert status == 200
    assert g["gate"]["passed"] is False
    assert g["gate"]["exit_code"] == 1
    assert len(g["gate"]["reasons"]) >= 1


def test_gate_v2_fails_against_v1_baseline(server):
    _, g1 = _post(server, "/api/gate", {"content": V1, "policy": "STRICT"})
    status, g2 = _post(server, "/api/gate",
                       {"content": V2, "policy": "STRICT",
                        "baseline": g1["result"]})
    assert status == 200
    assert g2["gate"]["passed"] is False
    assert any("new blocker" in r for r in g2["gate"]["reasons"])


def test_gate_empty_content_400(server):
    status, err = _post(server, "/api/gate", {"content": ""})
    assert status == 400


# ── /api/report ──────────────────────────────────────────────────────────────

def test_report_html_contains_real_findings(server):
    status, r = _post(server, "/api/report", {"content": V2, "format": "html"})
    assert status == 200
    assert "UPF-061" in r["content"]
    assert "Readiness" in r["content"] or "BLOCKED" in r["content"]


def test_report_json_is_valid_evidence(server):
    status, r = _post(server, "/api/report", {"content": V2, "format": "json"})
    assert status == 200
    parsed = json.loads(r["content"])
    assert parsed["check"]["counts"]["errors"] >= 1


def test_report_bad_format_400(server):
    status, err = _post(server, "/api/report",
                        {"content": V2, "format": "pdf"})
    assert status == 400


# ── /api/sample ──────────────────────────────────────────────────────────────

def test_sample_serves_fixtures(server):
    for name in ("cpu_v1", "cpu_v2", "cpu_design"):
        status, s = _get(server, f"/api/sample?name={name}")
        assert status == 200
        assert s["name"] == name
        assert len(s["content"]) > 100


def test_sample_traversal_rejected(server):
    status, _ = _get(server, "/api/sample?name=../../pyproject.toml")
    assert status == 404


def test_sample_unknown_404(server):
    status, _ = _get(server, "/api/sample?name=nope")
    assert status == 404


# ── design-aware normalization ───────────────────────────────────────────────

def _read_design():
    with open(os.path.join(FIX, "cpu_subsys_design.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_validate_with_dict_design_runs_design_aware(server):
    # The web API passes design context as a plain dict. It must be
    # normalized to DesignContext so the design-aware layer runs (readiness
    # mode flips, no crash) instead of silently degrading.
    status, res = _post(server, "/api/validate",
                        {"content": V1, "design": _read_design()})
    assert status == 200
    assert res["readiness"]["mode"] == "DESIGN_AWARE"
    assert res["check"]["counts"]["errors"] == 0


def test_validate_without_design_stays_upf_only(server):
    status, res = _post(server, "/api/validate", {"content": V1})
    assert status == 200
    assert res["readiness"]["mode"] == "UPF_ONLY"
