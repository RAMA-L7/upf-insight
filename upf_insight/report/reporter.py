"""Reporting — text, JSON, JUnit XML, and HTML for UPF validation results."""

from __future__ import annotations

import html
import json
import xml.etree.ElementTree as ET
from typing import List

from ..engine.engine import ValidateResult
from ..engine.rules.checker import Finding


def format_text(result: ValidateResult) -> str:
    lines: list[str] = [
        "UPF-Insight — deterministic power-intent validation",
        "==================================================",
        f"Files:  {result.file_count}   Commands: {result.command_count}",
        "",
    ]

    findings: list[Finding] = result.check.findings
    if not findings:
        lines.append("No findings.")
    else:
        for f in findings:
            loc = f"{f.file}:{f.line}" if f.line else (f.file or "-")
            lines.append(f"[{f.severity.upper():7}] {f.rule:8} {loc:40} "
                         f"{f.message}  (support={f.support})")
    lines.append("")

    if result.support:
        statuses = result.support.statuses
        active = {k: v for k, v in statuses.items() if v}
        lines.append("Support boundary:")
        for k, v in active.items():
            lines.append(f"  {k}: {v}")
        for note in result.support.notes:
            lines.append(f"  note: {note}")

    if result.pst:
        lines.append("")
        lines.append("PST: " + result.pst.coverage_note)

    if result.readiness:
        lines.append("")
        lines.append("Readiness: " + result.readiness.overall)
        for dim, ev in result.readiness.dimensions.items():
            lines.append(f"  {dim}: {ev.status} — {ev.summary}")

    if result.coverage and result.coverage.domains:
        lines.append("")
        lines.append(f"Coverage: domain {result.coverage.domain_coverage} "
                     f"supply {result.coverage.supply_coverage}")
        for d in result.coverage.domains:
            lines.append(f"  {d.domain}: "
                         f"{'covered' if d.covered else 'GAPS: ' + ', '.join(d.gaps)}")

    lines.append("")
    lines.append(f"Summary: {result.check.error_count} error(s), "
                 f"{result.check.warning_count} warning(s), "
                 f"{result.check.info_count} info(s) — "
                 f"{'PASS' if result.clean else 'FAIL'}")
    return "\n".join(lines) + "\n"


def format_json(result: ValidateResult) -> str:
    return json.dumps(result.to_dict(), indent=2, default=str)


def format_junit(result: ValidateResult) -> str:
    """JUnit XML for CI — one testcase per rule, failures for error/warning."""
    suite = ET.Element("testsuite", {
        "name": "upf-insight",
        "tests": str(len(result.check.findings)),
        "failures": str(result.check.error_count + result.check.warning_count),
        "errors": "0",
    })
    for f in result.check.findings:
        case = ET.SubElement(suite, "testcase", {
            "classname": f.rule,
            "name": f.rule,
        })
        body = f"{f.message}  ({f.file}:{f.line})"
        if f.severity == "error" or f.severity == "warning":
            ET.SubElement(case, "failure", {"type": f.severity}).text = body
        else:
            ET.SubElement(case, "system-out").text = body
    return ET.tostring(suite, encoding="unicode")


def format_html(result: ValidateResult) -> str:
    """Standalone self-contained HTML report."""
    findings_rows = []
    for f in result.check.findings:
        loc = f"{f.file}:{f.line}" if f.line else (f.file or "-")
        findings_rows.append(
            f"<tr class='{f.severity}'>"
            f"<td>{html.escape(f.rule)}</td>"
            f"<td>{f.severity}</td>"
            f"<td>{html.escape(loc)}</td>"
            f"<td>{html.escape(f.message)}</td>"
            f"<td>{f.support}</td></tr>")
    findings_html = "\n".join(findings_rows) or "<tr><td colspan=5>No findings.</td></tr>"

    readiness_html = ""
    if result.readiness:
        dims = []
        for dim, ev in result.readiness.dimensions.items():
            dims.append(
                f"<div class='dim'><b>{html.escape(dim)}</b>: {ev.status}"
                f"<div class='muted'>{html.escape(ev.summary)}</div></div>")
        readiness_html = ("<h2>Readiness</h2>"
                          f"<div class='verdict {result.readiness.overall}'>"
                          f"{result.readiness.overall}</div>"
                          + "\n".join(dims))

    support_html = ""
    if result.support:
        statuses = " ".join(
            f"<span class='chip'>{k}: {v}</span>"
            for k, v in result.support.statuses.items() if v)
        support_html = f"<h2>Support boundary</h2><div>{statuses}</div>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>UPF-Insight report</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
 h1 {{ font-size: 1.5rem; }}
 table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
 th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #e5e7eb; }}
 th {{ background: #f3f4f6; }}
 tr.error td:first-child {{ border-left: 4px solid #dc2626; }}
 tr.warning td:first-child {{ border-left: 4px solid #d97706; }}
 tr.info td:first-child {{ border-left: 4px solid #2563eb; }}
 .verdict {{ display: inline-block; padding: 0.5rem 1rem; border-radius: 6px;
             color: white; font-weight: 700; }}
 .BLOCKED {{ background: #dc2626; }}
 .REVIEW_REQUIRED {{ background: #d97706; }}
 .READY_WITH_ADVISORIES {{ background: #2563eb; }}
 .READY {{ background: #059669; }}
 .INSUFFICIENT_CONTEXT {{ background: #6b7280; }}
 .dim {{ margin: 0.5rem 0; }}
 .muted {{ color: #6b7280; font-size: 0.85rem; }}
 .chip {{ display: inline-block; background: #f3f4f6; padding: 0.2rem 0.5rem;
          border-radius: 4px; margin-right: 0.4rem; }}
</style></head><body>
<h1>UPF-Insight — power-intent validation report</h1>
<p class="muted">Files: {result.file_count} · Commands: {result.command_count} ·
Summary: {result.check.error_count} error(s), {result.check.warning_count}
warning(s), {result.check.info_count} info(s)</p>
{readiness_html}
{support_html}
<h2>Findings</h2>
<table><thead><tr><th>Rule</th><th>Severity</th><th>Location</th>
<th>Message</th><th>Support</th></tr></thead>
<tbody>{findings_html}</tbody></table>
</body></html>"""


__all__ = ["format_text", "format_json", "format_junit", "format_html"]