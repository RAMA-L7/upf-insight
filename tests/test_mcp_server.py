"""MCP server tests: pure handle_request dispatch over newline-delimited JSON-RPC.

The server must expose every engine tool (validate, model, pst, coverage,
relations, analyze, report, diff, generate, rules, rule_show, rules_audit,
gate, batch, lint, convert, quality, whats_new, version), answer
initialize/ping, return -32601 for unknown methods, map engine failures to
isError tool results (never crashes), and stay silent (None) for notifications.
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


def test_tools_list_exposes_every_engine_tool(state):
    """Every CLI/API feature must be reachable as an MCP tool."""
    resp = handle_request(state, _request("tools/list"))
    names = [t["name"] for t in resp["result"]["tools"]]
    assert len(names) == 19
    expected = {
        # original eight
        "upf_validate", "upf_model", "upf_pst", "upf_coverage",
        "upf_diff", "upf_generate", "upf_rules", "upf_gate",
        # one per remaining CLI/API feature
        "upf_relations",   # relations
        "upf_analyze",     # analyze (end-to-end + optional netlist)
        "upf_report",      # report (json/text/html)
        "upf_rule_show",   # rules show CODE
        "upf_rules_audit", # rules audit
        "upf_batch",       # batch check
        "upf_lint",        # lint (read-only)
        "upf_convert",     # convert to json/yaml
        "upf_quality",     # quality (mutation corpus)
        "upf_whats_new",   # whats-new
        "upf_version",     # /api/version
    }
    assert set(names) == expected, set(names) ^ expected
    # every schema must carry a description so an agent can choose a tool
    for tool in resp["result"]["tools"]:
        assert tool.get("description"), tool["name"]


def _call(state, name, arguments=None, request_id=1):
    """Call a tool and return (isError, parsed_payload).

    Successful tools return a JSON payload; engine failures come back as
    ``isError=True`` with plain ``error: ...`` text, so only decode JSON when
    it is actually there.
    """
    resp = handle_request(state, _request(
        "tools/call", {"name": name, "arguments": arguments or {}},
        request_id=request_id))
    body = resp["result"]
    text = body["content"][0]["text"]
    if body["isError"]:
        return True, text
    return False, json.loads(text)


def test_tool_relations_returns_matrix(state):
    err, body = _call(state, "upf_relations", {"path": FIXTURE})
    assert err is False
    assert "relations" in body and body["relations"] is not None


def test_tool_analyze_summary(state):
    err, body = _call(state, "upf_analyze", {"path": FIXTURE})
    assert err is False
    summary = body["summary"]
    assert summary["files"] == 1 and "readiness" in summary
    assert "result" in body


def test_tool_report_formats(state):
    for fmt in ("json", "text", "html"):
        err, body = _call(state, "upf_report",
                          {"path": FIXTURE, "format": fmt})
        assert err is False and body["format"] == fmt
        assert body["report"]


def test_tool_report_rejects_bad_format(state):
    err, _ = _call(state, "upf_report", {"path": FIXTURE, "format": "xml"})
    assert err is True


def test_tool_rule_show_is_case_insensitive(state):
    err, body = _call(state, "upf_rule_show", {"code": "upf-038"})
    assert err is False and body["code"] == "UPF-038"
    assert body["description"] and body["test_ref"]


def test_tool_rule_show_unknown_code_is_tool_error(state):
    err, _ = _call(state, "upf_rule_show", {"code": "UPF-999"})
    assert err is True


def test_tool_rules_audit_is_clean(state):
    err, body = _call(state, "upf_rules_audit", {})
    assert err is False and body["clean"] is True


def test_tool_batch_counts_directory(state):
    err, body = _call(state, "upf_batch", {"path": "tests/examples"})
    assert err is False
    assert body["total_files"] >= 10
    assert body["passed"] + body["failed"] == body["total_files"]


def test_tool_batch_rejects_file_not_directory(state):
    err, _ = _call(state, "upf_batch", {"path": FIXTURE})
    assert err is True


def test_tool_lint_is_read_only(state, tmp_path):
    """upf_lint must never rewrite the file it inspects."""
    src = tmp_path / "lint_me.upf"
    original = "upf_version 3.0\ncreate_power_domain PD_A\n"
    src.write_text(original, encoding="utf-8")
    state2 = McpState(root=str(tmp_path))
    err, body = _call(state2, "upf_lint", {"path": "lint_me.upf"})
    assert err is False and "issues" in body
    assert src.read_text(encoding="utf-8") == original  # untouched


def test_tool_convert_both_formats(state):
    for fmt in ("json", "yaml"):
        err, body = _call(state, "upf_convert",
                          {"path": FIXTURE, "format": fmt})
        assert err is False and body["format"] == fmt and body["text"]


def test_tool_quality_full_corpus(state):
    err, body = _call(state, "upf_quality", {})
    assert err is False
    assert body["total_mutations"] >= 40
    assert body["detected"] == body["total_mutations"] - len(body["missed"])


def test_tool_whats_new_all_and_default(state):
    err, few = _call(state, "upf_whats_new", {})
    assert err is False and len(few["releases"]) <= 3
    err, allr = _call(state, "upf_whats_new", {"all": True})
    assert err is False and len(allr["releases"]) >= len(few["releases"])
    assert "installed_version" in allr


def test_tool_version(state):
    from upf_insight import __version__

    err, body = _call(state, "upf_version", {})
    assert err is False and body == {"name": "upf-insight",
                                     "version": __version__}


def test_new_tools_bound_paths_too(state):
    """The added tools must enforce the same workspace-root guard."""
    for name, args in (("upf_lint", {"path": "../../etc/passwd"}),
                       ("upf_convert", {"path": "../../etc/passwd"}),
                       ("upf_batch", {"path": "../../etc"}),
                       ("upf_report", {"path": "../../etc/passwd"}),
                       ("upf_analyze", {"path": "../../etc/passwd"}),
                       ("upf_relations", {"path": "../../etc/passwd"})):
        err, _ = _call(state, name, args)
        assert err is True, name


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


def test_serve_survives_client_disconnect():
    """A closed stdout must end the loop quietly, not raise.

    Hosts shut down mid-session; the module contract says the serve loop
    never crashes. Writing to a dead pipe used to raise OSError out of
    stdout.flush() and kill the server.
    """
    from upf_insight.api.mcp_server import serve

    class _DeadPipe:
        def write(self, _s):
            raise OSError(22, "Invalid argument")

        def flush(self):
            raise OSError(22, "Invalid argument")

    requests = "".join(
        json.dumps({"jsonrpc": "2.0", "id": i, "method": "ping"}) + "\n"
        for i in range(3))
    # Must return without raising despite every write failing.
    serve(stdin=__import__("io").StringIO(requests), stdout=_DeadPipe())


def test_serve_still_writes_when_pipe_is_open():
    """Control for the disconnect test: an open pipe still gets responses."""
    import io

    from upf_insight.api.mcp_server import serve

    out = io.StringIO()
    serve(stdin=io.StringIO(json.dumps(
        {"jsonrpc": "2.0", "id": 7, "method": "ping"}) + "\n"), stdout=out)
    response = json.loads(out.getvalue().strip())
    assert response["id"] == 7 and response["result"] == {}
