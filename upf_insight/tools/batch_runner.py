"""Batch validation - validate every UPF/Tcl file under a root directory.

Deterministic (sorted file order), robust to unreadable files (recorded as
failures, never aborting the run), and reuses the engine + reporter so batch
output is byte-identical to single-file runs.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..engine.engine import ValidateResult, validate
from ..report.reporter import format_html, format_json, format_text

UPF_EXTENSIONS: frozenset[str] = frozenset({".upf", ".tcl"})

_RENDERERS: Dict[str, Callable[[ValidateResult], str]] = {
    "text": format_text,
    "json": format_json,
    "html": format_html,
}


def iter_upf_files(root: Path) -> list[Path]:
    """Recursively collect .upf/.tcl files under root, sorted for determinism."""
    r = Path(root)
    files: List[Path] = [
        p for p in r.rglob("*")
        if p.is_file() and p.suffix.lower() in UPF_EXTENSIONS
    ]
    return sorted(files)


@dataclass
class BatchResult:
    """Aggregate outcome of validating a directory of UPF files."""

    total_files: int = 0
    passed: int = 0
    failed: int = 0
    per_file: List[Dict[str, object]] = field(default_factory=list)
    outputs: Dict[str, str] = field(default_factory=dict)


@dataclass
class BatchReportResult:
    """Written artifacts of an HTML batch report run."""

    output_dir: Path
    total_files: int = 0
    passed: int = 0
    failed: int = 0
    reports: List[str] = field(default_factory=list)


def _render(result: ValidateResult, fmt: str) -> str:
    renderer = _RENDERERS.get(fmt)
    if renderer is None:
        raise ValueError(f"unsupported format: {fmt!r} "
                         f"(expected one of {sorted(_RENDERERS)})")
    return renderer(result)


def _check_one(path: Path, rules: Optional[List[str]],
               fmt: str) -> tuple[Dict[str, object], str]:
    result = validate([str(path)], rules=rules)
    clean = result.clean
    entry: Dict[str, object] = {
        "file": str(path),
        "exit_status": 0 if clean else 1,
        "error_count": result.check.error_count,
        "warning_count": result.check.warning_count,
    }
    return entry, _render(result, fmt)


def _failure_entry(path: Path, exc: BaseException) -> Dict[str, object]:
    detail = f"{type(exc).__name__}: {exc}"
    return {
        "file": str(path),
        "exit_status": 3,
        "error_count": 1,
        "warning_count": 0,
        "error": detail,
        "traceback": traceback.format_exc(),
    }


def batch_check(root: Path, rules: Optional[List[str]] = None,
                format: str = "text") -> BatchResult:
    """Validate each UPF/Tcl file under root; one bad file never stops the run."""
    result = BatchResult()
    if format not in _RENDERERS:
        raise ValueError(f"unsupported format: {format!r} "
                         f"(expected one of {sorted(_RENDERERS)})")
    files = iter_upf_files(root)
    result.total_files = len(files)
    for path in files:
        try:
            entry, rendered = _check_one(path, rules, format)
        except Exception as exc:
            entry = _failure_entry(path, exc)
            rendered = ""
        status = int(entry["exit_status"])  # type: ignore[arg-type]
        if status == 0:
            result.passed += 1
        else:
            result.failed += 1
        result.per_file.append(entry)
        result.outputs[str(path)] = rendered
    return result


def _report_filename(rel: Path) -> str:
    parts = [p for p in rel.parts if p not in ("", ".", "..")]
    safe = "__".join(parts).replace(":", "_")
    stem = Path(safe).stem if safe else "file"
    suffix = Path(safe).suffix.lower()
    if suffix in UPF_EXTENSIONS:
        suffix = ".html"
    else:
        suffix = suffix.replace(".", "_") + ".html"
    return stem + suffix


def batch_report(root: Path, output_dir: Path) -> BatchReportResult:
    """Write per-file HTML reports plus an index.html; return written paths."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    passed = 0
    failed = 0
    rows: List[str] = []
    files = iter_upf_files(root)
    for path in files:
        base = Path(root)
        try:
            rel = path.relative_to(base)
        except ValueError:
            rel = path
        page_name = _report_filename(rel)
        try:
            result = validate([str(path)])
            html_text = format_html(result)
            status = "PASS" if result.clean else "FAIL"
            summary = (f"{result.check.error_count} error(s), "
                       f"{result.check.warning_count} warning(s)")
            if result.clean:
                passed += 1
            else:
                failed += 1
            exit_status = 0 if result.clean else 1
        except Exception as exc:
            html_text = ("<!doctype html><html><head><meta charset='utf-8'>"
                         "<title>UPF-Insight report error</title></head><body>"
                         f"<h1>Validation error</h1>"
                         f"<pre>{type(exc).__name__}: {exc}</pre>"
                         "</body></html>")
            status = "ERROR"
            summary = f"{type(exc).__name__}: {exc}"
            exit_status = 3
            failed += 1
        page_path = out_dir / page_name
        page_path.write_text(html_text, encoding="utf-8")
        written.append(str(page_path))
        rows.append(
            f"<tr class='{status.lower()}'><td>"
            f"<a href='{page_name}'>{rel.as_posix()}</a></td>"
            f"<td>{status}</td><td>{summary}</td>"
            f"<td>exit {exit_status}</td></tr>")
    index_rows = "\n".join(rows) or (
        "<tr><td colspan='4'>No .upf/.tcl files found.</td></tr>")
    index_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>UPF-Insight batch report</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
 table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
 th, td {{ text-align: left; padding: 0.4rem 0.6rem;
           border-bottom: 1px solid #e5e7eb; }}
 th {{ background: #f3f4f6; }}
 tr.pass td:nth-child(2) {{ color: #059669; font-weight: 700; }}
 tr.fail td:nth-child(2), tr.error td:nth-child(2)
   {{ color: #dc2626; font-weight: 700; }}
</style></head><body>
<h1>UPF-Insight batch report</h1>
<p>Root: {Path(root)} &middot; Files: {len(files)} &middot;
Passed: {passed} &middot; Failed/Errored: {failed}</p>
<table><thead><tr><th>File</th><th>Status</th><th>Summary</th>
<th>Exit</th></tr></thead>
<tbody>
{index_rows}
</tbody></table>
</body></html>"""
    index_path = out_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    written.append(str(index_path))
    return BatchReportResult(output_dir=out_dir, total_files=len(files),
                             passed=passed, failed=failed,
                             reports=sorted(written))


__all__ = ["BatchReportResult", "BatchResult", "batch_check", "batch_report",
           "iter_upf_files"]
