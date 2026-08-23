"""MCP server for UPF-Insight - JSON-RPC 2.0 over stdio (stdlib-only).

Exposes the deterministic engine as Model Context Protocol tools without any
third-party SDK: newline-delimited JSON-RPC 2.0 on stdin/stdout. The analysis
path is the same engine used by the CLI and web API, so every tool result is
real evidence with line-level provenance. Engine failures are reported as
tool results with ``isError=True``; protocol errors use JSON-RPC error objects
and never crash the serve loop.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .. import __version__
from ..engine.engine import validate

_PROTOCOL_VERSION = "2024-11-05"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


@dataclass
class McpState:
    """Server state: workspace root bounding user-supplied file paths."""

    root: str = ""

    def __post_init__(self) -> None:
        if not self.root:
            self.root = os.path.realpath(
                os.environ.get("UPF_INSIGHT_WORKSPACE") or os.getcwd()
            )


def _bounded(state: McpState, path: str) -> Optional[str]:
    root = os.path.realpath(state.root)
    candidate = os.path.realpath(os.path.join(root, path))
    if candidate == root or candidate.startswith(root + os.sep):
        return candidate
    return None


def _require_path(state: McpState, args: dict, key: str = "path") -> str:
    raw = args.get(key)
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"'{key}' must be a non-empty string path")
    bounded = _bounded(state, raw)
    if bounded is None:
        raise ValueError(f"path outside workspace root: {raw}")
    if not os.path.isfile(bounded):
        raise ValueError(f"file not found: {raw}")
    return bounded


def _tool_upf_validate(state: McpState, args: dict) -> dict:
    netlist_raw = args.get("netlist")
    netlist: Optional[str] = None
    if netlist_raw is not None:
        netlist = _require_path(state, args, "netlist")
    content = args.get("content")
    if content is not None:
        from ..engine.engine import validate_records
        from ..preprocess.upf_preprocess import preprocess

        if not isinstance(content, str) or not content.strip():
            raise ValueError("'content' must be non-empty UPF text")
        result = validate_records(preprocess(content, file=args.get("file", "<mcp>")))
    else:
        result = validate([_require_path(state, args)], netlist=netlist)
    return result.to_dict()


def _tool_upf_model(state: McpState, args: dict) -> dict:
    from ..model.builder import build_model
    from ..preprocess.upf_preprocess import preprocess_many

    records = preprocess_many([_require_path(state, args)])
    model = build_model(records)
    return {"model": model.to_dict(), "command_count": model.commands_seen}


def _tool_upf_pst(state: McpState, args: dict) -> dict:
    result = validate([_require_path(state, args)])
    return {"pst": result.pst.to_dict() if result.pst else None,
            "readiness": result.readiness.to_dict() if result.readiness else None}


def _tool_upf_coverage(state: McpState, args: dict) -> dict:
    result = validate([_require_path(state, args)])
    return {"coverage": result.coverage.to_dict() if result.coverage else None}


def _tool_upf_diff(state: McpState, args: dict) -> dict:
    from ..diff.differ import diff_files

    old_path = _require_path(state, args, "old_path")
    new_path = _require_path(state, args, "new_path")
    changes = diff_files(old_path, new_path)
    return {"changes": [
        {"kind": c.kind, "what": c.what, "name": c.name, "detail": c.detail}
        for c in changes
    ]}


def _build_params(raw: dict) -> Any:
    from ..generate.generator import (
        UPFParams,
        DomainParam,
        SwitchParam,
        IsolationParam,
        LevelShifterParam,
        RetentionParam,
        RepeaterParam,
        RelationParam,
        PstStateParam,
    )

    params = UPFParams(
        design_top=raw.get("design_top", "top"),
        upf_version=raw.get("upf_version", "3.0"),
        primary_power=raw.get("primary_power", "vdd"),
        primary_ground=raw.get("primary_ground", "vss"),
        on_voltage=raw.get("on_voltage", 1.0),
        off_voltage=raw.get("off_voltage", 0.0),
        domains=[DomainParam(**d) for d in raw.get("domains", [])],
        switches=[SwitchParam(**s) for s in raw.get("switches", [])],
        isolation=[IsolationParam(**i) for i in raw.get("isolation", [])],
        level_shifters=[LevelShifterParam(**l) for l in raw.get("level_shifters", [])],
        retention=[RetentionParam(**r) for r in raw.get("retention", [])],
        repeaters=[RepeaterParam(**r) for r in raw.get("repeaters", [])],
        pst_name=raw.get("pst_name", "pst_top"),
        always_on=list(raw.get("always_on", [])),
    )
    if raw.get("pst_states"):
        params.pst_states = [PstStateParam(**s) for s in raw["pst_states"]]
    params.relations = [
        RelationParam(from_domain=r.get("from_domain", ""),
                      to_domain=r.get("to_domain", ""),
                      kinds=r.get("kinds", "isolation"))
        for r in raw.get("relations", [])
    ]
    params.architecture = raw.get("architecture", "flat")
    params.hierarchy = [str(h) for h in raw.get("hierarchy", [])]
    return params


def _tool_upf_generate(state: McpState, args: dict) -> dict:
    from ..generate.generator import generate_upf

    raw = args.get("params")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("'params' must be an object")
    content = generate_upf(_build_params(raw))
    return {"content": content}


def _tool_upf_rules(state: McpState, args: dict) -> dict:
    from ..engine.rules.rules_registry import registered_rules

    return {"rules": [
        {"code": r.code, "severity": r.severity, "layer": r.layer,
         "title": r.title, "description": r.description,
         "context": r.context, "semantic_inputs": list(r.semantic_inputs)}
        for r in registered_rules()
    ]}


def _load_baseline(state: McpState, baseline: Any) -> Optional[dict]:
    if baseline is None:
        return None
    if isinstance(baseline, dict):
        return baseline
    if isinstance(baseline, str):
        bounded = _bounded(state, baseline)
        if bounded is None or not os.path.isfile(bounded):
            raise ValueError(f"baseline file not found in workspace: {baseline}")
        with open(bounded, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if not isinstance(loaded, dict):
            raise ValueError("baseline file must contain a JSON object")
        return loaded
    raise ValueError("baseline must be an object or a workspace file path")


def _tool_upf_gate(state: McpState, args: dict) -> dict:
    from ..engine.policy.policy_engine import apply_policy, BUILTIN_POLICIES

    gate_name = args.get("gate", "BLOCKERS_ONLY")
    policy_raw = args.get("gate_policy")
    baseline = _load_baseline(state, args.get("baseline"))
    content = args.get("content")
    if content is not None:
        from ..engine.engine import validate_records
        from ..preprocess.upf_preprocess import preprocess

        if not isinstance(content, str) or not content.strip():
            raise ValueError("'content' must be non-empty UPF text")
        current = validate_records(preprocess(content, file="<mcp>"))
    else:
        current = validate([_require_path(state, args)])
    gate = apply_policy(gate_name, current.to_dict(), baseline,
                        policy_raw=policy_raw)
    return {
        "gate": gate.to_dict(),
        "result": current.to_dict(),
        "policies": sorted(BUILTIN_POLICIES),
    }


_TOOLS: List[dict] = [
    {
        "name": "upf_validate",
        "description": ("Validate a UPF file (path) or inline UPF text "
                        "(content) and return full engine evidence: findings, "
                        "support boundary, PST, readiness, coverage."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "netlist": {"type": "string"},
                "file": {"type": "string"},
            },
        },
    },
    {
        "name": "upf_model",
        "description": "Build the power-intent object model from a UPF file.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}},
                        "required": ["path"]},
    },
    {
        "name": "upf_pst",
        "description": "Analyze the Power State Table of a UPF file.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}},
                        "required": ["path"]},
    },
    {
        "name": "upf_coverage",
        "description": "Compute strategy coverage for a UPF file.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}},
                        "required": ["path"]},
    },
    {
        "name": "upf_diff",
        "description": "Semantic model-level diff between two UPF files.",
        "inputSchema": {
            "type": "object",
            "properties": {"old_path": {"type": "string"},
                           "new_path": {"type": "string"}},
            "required": ["old_path", "new_path"],
        },
    },
    {
        "name": "upf_generate",
        "description": "Generate a UPF skeleton from declarative parameters.",
        "inputSchema": {"type": "object", "properties": {"params": {"type": "object"}}},
    },
    {
        "name": "upf_rules",
        "description": "List every registered rule code with severity, layer "
                       "and description.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "upf_gate",
        "description": ("Run a CI gate policy against a UPF file (or inline "
                        "content), optionally compared to a saved baseline."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "baseline": {},
                "gate": {"type": "string"},
                "gate_policy": {"type": "object"},
            },
        },
    },
]

_HANDLERS: Dict[str, Callable[[McpState, dict], dict]] = {
    "upf_validate": _tool_upf_validate,
    "upf_model": _tool_upf_model,
    "upf_pst": _tool_upf_pst,
    "upf_coverage": _tool_upf_coverage,
    "upf_diff": _tool_upf_diff,
    "upf_generate": _tool_upf_generate,
    "upf_rules": _tool_upf_rules,
    "upf_gate": _tool_upf_gate,
}


def _rpc_result(request_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def _call_tool(state: McpState, request_id: Any, params: Any) -> dict:
    if not isinstance(params, dict):
        return _rpc_error(request_id, INVALID_PARAMS,
                          "'params' must be an object with 'name'/'arguments'")
    name = params.get("name")
    handler = _HANDLERS.get(name)
    if handler is None:
        known = ", ".join(sorted(_HANDLERS))
        return _rpc_error(request_id, INVALID_PARAMS,
                          f"unknown tool: {name!r}; available: {known}")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return _rpc_error(request_id, INVALID_PARAMS,
                          "'arguments' must be an object")
    try:
        payload = handler(state, arguments)
    except Exception as exc:
        body = {"content": [{"type": "text", "text": f"error: {exc}"}],
                "isError": True}
    else:
        body = {"content": [{"type": "text",
                             "text": json.dumps(payload, indent=2, default=str)}],
                "isError": False}
    return _rpc_result(request_id, body)


def handle_request(state: McpState, request_dict: Any) -> Optional[dict]:
    """Pure JSON-RPC 2.0 dispatcher (no stdin/stdout access).

    Returns a response dict, or None when the message is a notification
    (no ``id`` member).
    """
    if not isinstance(request_dict, dict):
        return _rpc_error(None, INVALID_REQUEST, "request must be a JSON object")
    if request_dict.get("jsonrpc") != "2.0":
        return _rpc_error(request_dict.get("id"), INVALID_REQUEST,
                          "'jsonrpc' must be exactly '2.0'")
    method = request_dict.get("method")
    if method is None:
        return _rpc_error(request_dict.get("id"), INVALID_REQUEST,
                          "'method' is required")
    request_id = request_dict.get("id")
    is_notification = "id" not in request_dict

    if method == "initialize":
        return _rpc_result(request_id, {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "upf-insight", "version": __version__},
        })
    if method == "ping":
        return _rpc_result(request_id, {})
    if method == "tools/list":
        return _rpc_result(request_id, {"tools": [dict(t) for t in _TOOLS]})
    if method == "tools/call":
        response = _call_tool(state, request_id, request_dict.get("params"))
        return None if is_notification else response
    if is_notification:
        return None
    return _rpc_error(request_id, METHOD_NOT_FOUND, f"unknown method: {method!r}")


def serve(stdin: Any = None, stdout: Any = None) -> None:
    """Newline-delimited JSON-RPC 2.0 loop over stdio. Never crashes on bad input."""
    if stdin is None:
        stdin = sys.stdin
    if stdout is None:
        stdout = sys.stdout
    state = McpState()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _rpc_error(None, PARSE_ERROR, f"parse error: {exc}")
        else:
            try:
                response = handle_request(state, request)
            except Exception as exc:
                rid = request.get("id") if isinstance(request, dict) else None
                response = _rpc_error(rid, INVALID_REQUEST, f"internal error: {exc}")
        if response is not None:
            stdout.write(json.dumps(response, default=str) + "\n")
            stdout.flush()


__all__ = ["McpState", "serve", "handle_request"]
