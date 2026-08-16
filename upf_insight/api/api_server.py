"""Local HTTP API server (stdlib-only) serving the UPF-Insight workspace.

Mirrors the sdc-tools api_server pattern: a small stdlib http.server JSON API
so the vanilla-JS workspace can run validation without any EDA tool, Python
framework, or network egress.
"""

from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict
from urllib.parse import parse_qs, urlparse

from .. import __version__
from ..engine.engine import validate

_WEB_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "workspace", "webui"))

# Workspace root that user-supplied file paths (files / netlist) are bounded to.
# Defaults to the launch directory; override with UPF_INSIGHT_WORKSPACE.
_WORKSPACE_ROOT = os.path.realpath(
    os.environ.get("UPF_INSIGHT_WORKSPACE") or os.getcwd()
)


def _bounded(root: str, path: str):
    """Return the realpath of ``path`` only if it stays inside ``root``.

    Local File Inclusion guard: ``realpath`` collapses ``..`` and symlinks; the
    candidate is accepted only when it equals the root or lives beneath it.
    """
    root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root, path))
    if candidate == root or candidate.startswith(root + os.sep):
        return candidate
    return None

# Theme / status metadata served to the workspace (single source of truth).
_DESIGN = {
    "version": __version__,
    "severity": {
        "fatal": {"label": "FATAL", "color": "error", "shape": "octagon"},
        "error": {"label": "ERROR", "color": "error", "shape": "octagon"},
        "warning": {"label": "WARNING", "color": "warning", "shape": "triangle"},
        "info": {"label": "INFO", "color": "info", "shape": "circle"},
    },
    "trust": {
        "VALIDATED": {"label": "VALIDATED", "color": "success", "shape": "square"},
        "PARTIALLY_VALIDATED": {"label": "PARTIAL", "color": "warning", "shape": "square-half"},
        "NETLIST_REQUIRED": {"label": "NETLIST", "color": "info", "shape": "square-net"},
        "TCL_EXECUTION_REQUIRED": {"label": "TCL EXEC", "color": "unknown", "shape": "square-term"},
        "UNSUPPORTED": {"label": "UNSUPPORTED", "color": "error", "shape": "slash"},
        "NOT_VALIDATED": {"label": "NOT CHECKED", "color": "unknown", "shape": "square-hollow"},
    },
    "readiness": {
        "READY": {"label": "READY", "color": "success", "shape": "shield"},
        "READY_WITH_ADVISORIES": {"label": "READY+", "color": "success", "shape": "shield-dot"},
        "REVIEW_REQUIRED": {"label": "REVIEW", "color": "warning", "shape": "triangle"},
        "BLOCKED": {"label": "BLOCKED", "color": "error", "shape": "octagon"},
        "INSUFFICIENT_CONTEXT": {"label": "LIMITED", "color": "unknown", "shape": "shield-hollow"},
        "NOT_APPLICABLE": {"label": "N/A", "color": "muted", "shape": "square-hollow"},
    },
    "colors": {
        "background_primary": "#FFFFFF", "background_secondary": "#FAFAFA",
        "surface": "#FFFFFF", "border_subtle": "#E6E6E6", "border_active": "#C9C9C9",
        "text_primary": "#000000", "text_secondary": "#333333", "text_muted": "#808080",
        "accent_primary": "#000000", "accent_secondary": "#000000",
        "success": "#1A1A1A", "warning": "#555555", "error": "#000000", "info": "#2E2E2E",
    },
}



class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def _send_json(self, obj: Dict, status: int = 200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    _CONTENT_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".ico": "image/x-icon",
    }

    def _send_file(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        ctype = self._CONTENT_TYPES.get(ext, "application/octet-stream")
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_file(os.path.join(_WEB_DIR, "index.html"))
        elif parsed.path.startswith("/assets/"):
            rel = parsed.path[len("/assets/"):]
            target = _bounded(os.path.join(_WEB_DIR, "assets"), rel)
            if target is None:
                self.send_error(403)
                return
            self._send_file(target)
        elif parsed.path == "/api/version":
            self._send_json({"name": "upf-insight", "version": __version__})
        elif parsed.path == "/api/design":
            self._send_json(_DESIGN)
        elif parsed.path == "/api/rules":
            from ..engine.rules.rules_registry import registered_rules

            self._send_json({"rules": [r.__dict__ for r in registered_rules()]})
        elif parsed.path == "/api/sample":
            qs = parse_qs(parsed.query)
            name = (qs.get("name") or [""])[0]
            samples_root = os.path.realpath(
                os.path.join(_WEB_DIR, "..", "samples"))
            bounded = _bounded(samples_root, name)
            if bounded is None or not os.path.isfile(bounded):
                self.send_error(404)
                return
            with open(bounded, "r", encoding="utf-8") as fh:
                self._send_json({"name": name, "content": fh.read()})
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/validate":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            files = payload.get("files", [])
            content = payload.get("content")
            design = payload.get("design")
            if content is not None:
                from ..preprocess.upf_preprocess import preprocess
                from ..engine.engine import validate_records

                records = preprocess(content, file=payload.get("file", "<web>"))
                result = validate_records(records, design=design)
            else:
                safe_files = []
                for f in files:
                    bounded = _bounded(_WORKSPACE_ROOT, f)
                    if bounded is None:
                        self._send_json(
                            {"error": f"path outside workspace root: {f}"},
                            status=400,
                        )
                        return
                    safe_files.append(bounded)
                netlist = payload.get("netlist")
                if netlist:
                    bounded = _bounded(_WORKSPACE_ROOT, netlist)
                    if bounded is None:
                        self._send_json(
                            {"error": f"path outside workspace root: {netlist}"},
                            status=400,
                        )
                        return
                    netlist = bounded
                result = validate(safe_files, netlist=netlist)
            self._send_json(result.to_dict())
        elif parsed.path == "/api/generate":
            from ..generate.generator import (
                UPFParams,
                DomainParam,
                SwitchParam,
                IsolationParam,
                LevelShifterParam,
                RetentionParam,
                RepeaterParam,
                PstStateParam,
                generate_upf,
                generate_skeleton,
            )
            if self.command == "POST":
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                raw = payload.get("params") or {}
                try:
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
                    content = generate_upf(params)
                except (TypeError, ValueError) as exc:
                    self._send_json({"error": f"invalid generate params: {exc}"},
                                    status=400)
                    return
                self._send_json({"content": content})
            else:
                content = generate_skeleton(domains=["core", "io", "sram"],
                                            always_on=["clk", "rst"],
                                            retention=["core"])
                self._send_json({"content": content})
        elif parsed.path == "/api/diff":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            old_text = payload.get("old")
            new_text = payload.get("new")
            if not old_text or not new_text:
                self._send_json(
                    {"error": "both 'old' and 'new' UPF text are required"},
                    status=400,
                )
                return
            from ..preprocess.upf_preprocess import preprocess
            from ..engine.engine import validate_records
            from ..diff.differ import diff_models

            old_result = validate_records(
                preprocess(old_text, file=payload.get("old_file", "old.upf")))
            new_result = validate_records(
                preprocess(new_text, file=payload.get("new_file", "new.upf")))
            changes = diff_models(old_result.check.model, new_result.check.model)
            self._send_json({
                "changes": [
                    {"kind": c.kind, "what": c.what, "name": c.name,
                     "detail": c.detail}
                    for c in changes
                ],
                "old": {
                    "errors": old_result.check.error_count,
                    "warnings": old_result.check.warning_count,
                    "readiness": (old_result.readiness or {}).overall,
                },
                "new": {
                    "errors": new_result.check.error_count,
                    "warnings": new_result.check.warning_count,
                    "readiness": (new_result.readiness or {}).overall,
                },
            })
        elif parsed.path == "/api/gate":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            content = payload.get("content")
            if not content:
                self._send_json(
                    {"error": "UPF content is required to run the gate"},
                    status=400,
                )
                return
            from ..preprocess.upf_preprocess import preprocess
            from ..engine.engine import validate_records
            from ..engine.policy.policy_engine import (
                apply_policy,
                EXIT_PASS,
                EXIT_GATE_FAILED,
                EXIT_INVALID,
                BUILTIN_POLICIES,
            )

            current = validate_records(
                preprocess(content, file=payload.get("file", "<web>")),
                design=payload.get("design"),
            )
            policy = payload.get("policy") or "BLOCKERS_ONLY"
            baseline = payload.get("baseline")
            if baseline is not None and not isinstance(baseline, dict):
                self._send_json(
                    {"error": "baseline must be a JSON object (a saved result)"},
                    status=400,
                )
                return
            try:
                gate = apply_policy(policy, current.to_dict(), baseline)
            except ValueError as exc:
                self._send_json({"error": f"invalid policy: {exc}"},
                                status=400)
                return
            self._send_json({
                "gate": gate.to_dict(),
                "policies": sorted(BUILTIN_POLICIES),
                "result": current.to_dict(),
            })
        elif parsed.path == "/api/report":
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            content = payload.get("content")
            if not content:
                self._send_json(
                    {"error": "UPF content is required to generate a report"},
                    status=400,
                )
                return
            fmt = payload.get("format", "html")
            if fmt not in ("html", "json", "text"):
                self._send_json({"error": f"unsupported report format: {fmt}"},
                                status=400)
                return
            from ..preprocess.upf_preprocess import preprocess
            from ..engine.engine import validate_records
            from ..report.reporter import format_html, format_json, format_text

            result = validate_records(
                preprocess(content, file=payload.get("file", "<web>")),
                design=payload.get("design"),
            )
            body = {
                "html": format_html(result),
                "json": format_json(result),
                "text": format_text(result),
            }[fmt]
            self._send_json({"format": fmt, "content": body})
        else:
            self.send_error(404)


def serve(port: int = 8585) -> int:
    server, host = _build_server(port)
    url = f"http://{host}:{port}"
    print(f"UPF-Insight workspace: {url}")
    print("Press Ctrl+C to stop.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


class _DualStackServer(ThreadingHTTPServer):
    """IPv6 loopback accepting IPv4 too (localhost + 127.0.0.1 on one socket)."""

    address_family = 2  # AF_INET6; IPV6_V6ONLY=0 below admits IPv4

    def server_bind(self):
        import socket

        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def _build_server(port: int):
    """Bind IPv4 127.0.0.1 first (matches the printed URL and works everywhere);
    fall back to IPv6 dual-stack loopback only if IPv4 is unavailable."""
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        return server, "127.0.0.1"
    except OSError:
        server = _DualStackServer(("::1", port), Handler)
        return server, "127.0.0.1"


__all__ = ["serve"]