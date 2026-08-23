"""MCP server tests: pure handle_request dispatch over newline-delimited JSON-RPC.

The server must expose the 8 engine tools, answer initialize/ping, return
-32601 for unknown methods, map engine failures to isError tool results
(never crashes), and stay silent (None) for notifications.
"""

from __future__ import annotations

import json
import os

import pytest

from upf_insight.api.mcp_server import McpState, handle_request

FIXTURE = os.path.join("tests", "examples", "example.soc.upf")


@pytest.fixture()
def state() -> McpState:
    return McpState(root=os.getcwd())


def _request(method: str, params=None, request_id=1) -> dict:
    req = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        req["params"] = params
    return req


def test_initialize_returns_capabilities(state):
    resp = handle_request(state, _request("initialize"))
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert "capabilities" in resp["result"]
    assert resp["result"]["serverInfo"]["name"] == "upf-insight"
    assert "protocolVersion" in resp["result"]


def test_tools_list_exposes_eight_tools(state):
    resp = handle_request(state, _request("tools/list"))
    names = [t["name"] for t in resp["result"]["tools"]]
    assert len(names) == 8
    for expected in ("upf_validate", "upf_model", "upf_pst", "upf_coverage",
                     "upf_diff", "upf_generate", "upf_rules", "upf_gate"):
        assert expected in names


def test_tools_call_upf_rules_ok(state):
    resp = handle_request(
        state, _request("tools/call", {"name": "upf_rules", "arguments": {}}))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert resp["result"]["isError"] is False
    assert len(body["rules"]) >= 74
    codes = {r["code"] for r in body["rules"]}
    assert "UPF-001" in codes and "UPF-100" in codes


def test_tools_call_upf_validate_real_evidence(state):
    resp = handle_request(state, _request("tools/call", {
        "name": "upf_validate",
        "arguments": {"path": FIXTURE},
    }))
    assert resp["result"]["isError"] is False
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["file_count"] == 1
    assert "check" in body and "readiness" in body


def test_tools_call_engine_failure_is_error_not_crash(state):
    resp = handle_request(state, _request("tools/call", {
        "name": "upf_validate",
        "arguments": {"path": os.path.join("tests", "examples",
                                           "does_not_exist.upf")},
    }))
    assert resp["result"]["isError"] is True
    assert "error" in resp["result"]["content"][0]["text"].lower()


def test_tools_call_path_outside_workspace_is_tool_error(state):
    resp = handle_request(state, _request("tools/call", {
        "name": "upf_model",
        "arguments": {"path": "../../etc/passwd"},
    }))
    assert resp["result"]["isError"] is True


def test_unknown_method_is_32601(state):
    resp = handle_request(state, _request("no/such/method"))
    assert resp["error"]["code"] == -32601


def test_unknown_tool_is_invalid_params(state):
    resp = handle_request(state, _request(
        "tools/call", {"name": "upf_nope", "arguments": {}}))
    assert resp["error"]["code"] == -32602


def test_notification_returns_none(state):
    assert handle_request(
        state, {"jsonrpc": "2.0", "method": "tools/call",
                "params": {"name": "upf_rules", "arguments": {}}}) is None
    assert handle_request(
        state, {"jsonrpc": "2.0", "method": "initialized"}) is None


def test_ping_and_malformed_jsonrpc(state):
    assert handle_request(state, _request("ping"))["result"] == {}
    bad = _request("ping")
    bad["jsonrpc"] = "1.0"
    assert handle_request(state, bad)["error"]["code"] == -32600


def test_handle_request_is_pure(state, capsys):
    handle_request(state, _request("initialize"))
    handle_request(state, _request("tools/list"))
    handle_request(state, _request("tools/call",
                                   {"name": "upf_rules", "arguments": {}}))
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
