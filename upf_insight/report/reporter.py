"""Reporting - text, JSON, JUnit XML, and HTML for UPF validation results."""

from __future__ import annotations

import html
import json
import xml.etree.ElementTree as ET
from typing import List

from ..engine.engine import ValidateResult
from ..engine.rules.checker import Finding


def _primary_file(result: ValidateResult) -> str:
    """First finding's source file, else a neutral placeholder."""
    for f in result.check.findings:
        if f.file:
            return f.file
    return "design.upf"


def _next_hints(result: ValidateResult) -> List[str]:
    """Deterministic, engine-derived next actions for the text report."""
    file = _primary_file(result)
    hints: List[str] = []
    first_error = next((f for f in result.check.findings
                        if f.severity == "error"), None)
    if first_error:
        hints.append(f"inspect {first_error.rule}: "
                     f"upf-insight check {file} --rule {first_error.rule}")
    if not result.clean:
        hints.append(f"run strict gate: upf-insight check {file} --gate STRICT")
    hints.append(f"generate report: upf-insight report {file} -o report.html")
    return hints


def format_text(result: ValidateResult) -> str:
    mode = (result.readiness.mode if result.readiness else "UPF_ONLY")
    status = (result.readiness.overall if result.readiness
              else ("PASS" if result.clean else "FAIL"))
    lines: list[str] = [
        "UPF-Insight - deterministic power-intent validation",
        "==================================================",
        f"File       {_primary_file(result)}",
        f"Mode       {mode}",
        f"Status     {status}",
        f"Commands   {result.command_count}",
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
            lines.append(f"  {dim}: {ev.status} - {ev.summary}")

    if result.coverage and result.coverage.domains:
        lines.append("")
        lines.append(f"Coverage: domain {result.coverage.domain_coverage} "
                     f"supply {result.coverage.supply_coverage}")
        for d in result.coverage.domains:
            lines.append(f"  {d.domain}: "
                         f"{'covered' if d.covered else 'GAPS: ' + ', '.join(d.gaps)}")

    if result.relations is not None:
        rel = result.relations
        lines.append("")
        lines.append(f"Architecture : {rel.architecture}")
        n_sw = sum(1 for d in rel.domains if d.type == "SWITCHABLE")
        n_aon = sum(1 for d in rel.domains if d.type == "ALWAYS_ON")
        lines.append(f"Domains      : {len(rel.domains)} ({n_aon} always-on, "
                     f"{n_sw} switchable, "
                     f"{sum(1 for d in rel.domains if d.type == 'UNKNOWN')} unknown)")
        if rel.relations:
            lines.append("Relations     :")
            for r in rel.relations:
                ev = r.evidence[0] if r.evidence else None
                loc = f" L{ev.line}" if ev and ev.line else ""
                lines.append(f"  {r.from_domain} -> {r.to_domain}  "
                             f"{r.label}{loc}")
        if rel.supply_sharing:
            lines.append("Supply sharing:")
            for net in sorted(rel.supply_sharing):
                lines.append(f"  {net} -> "
                             + ", ".join(sorted(rel.supply_sharing[net])))
        if rel.hierarchy:
            lines.append("Hierarchy     :")
            for h in rel.hierarchy:
                lines.append(f"  {h['domain']}  scope={h['scope']}  "
                             f"file={h.get('upf_file') or '-'}")
        if rel.supply_maps:
            lines.append("Supply maps   :")
            for m in rel.supply_maps:
                lines.append(f"  {m['local']} -> {m['parent']} "
                             f"(scope {m['scope']}, L{m['line']})")

    lines.append("")
    lines.append(f"Summary: {result.check.error_count} error(s), "
                 f"{result.check.warning_count} warning(s), "
                 f"{result.check.info_count} info(s) - "
                 f"{'PASS' if result.clean else 'FAIL'}")
    hints = _next_hints(result)
    lines.append("")
    lines.append("Next:")
    for h in hints:
        lines.append(f"  -> {h}")  # ASCII-safe for Windows consoles
    return "\n".join(lines) + "\n"


def format_json(result: ValidateResult) -> str:
    return json.dumps(result.to_dict(), indent=2, default=str)


def format_junit(result: ValidateResult) -> str:
    """JUnit XML for CI - one testcase per rule, failures for error/warning."""
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

    relations_html = ""
    if result.relations is not None:
        rel = result.relations
        n_aon = sum(1 for d in rel.domains if d.type == "ALWAYS_ON")
        n_sw = sum(1 for d in rel.domains if d.type == "SWITCHABLE")
        rows = ""
        for r in rel.relations:
            ev = r.evidence[0] if r.evidence else None
            loc = f" L{ev.line}" if ev and ev.line else ""
            rows += (f"<tr><td>{html.escape(r.from_domain)} → "
                     f"{html.escape(r.to_domain)}</td><td><b>{html.escape(r.label)}</b>"
                     f"</td><td class='muted'>{html.escape(loc)}</td></tr>")
        relations_rows = rows or "<tr><td colspan=3>No proven cross-domain interactions.</td></tr>"
        matrix_rows = ""
        names = [d.name for d in rel.domains]
        if names:
            head = "<tr><th></th>" + "".join(
                f"<th>{html.escape(n)}</th>" for n in names) + "</tr>"
            body = ""
            for f in names:
                cells = "".join(
                    f"<td>{html.escape(rel.matrix.get(f, {}).get(t, ''))}"
                    f"</td>" for t in names)
                body += f"<tr><td class='muted'>{html.escape(f)}</td>{cells}</tr>"
            matrix_rows = head + body
        supply_rows = "".join(
            f"<tr><td class='muted'>{html.escape(net)}</td>"
            f"<td>{html.escape(', '.join(sorted(ds)))}</td></tr>"
            for net, ds in sorted(rel.supply_sharing.items()))
        hier_rows = "".join(
            f"<tr><td>{html.escape(h['domain'])}</td>"
            f"<td class='muted'>{html.escape(h.get('scope') or '-')}</td>"
            f"<td class='muted'>{html.escape(h.get('upf_file') or '-')}</td></tr>"
            for h in rel.hierarchy)
        relations_html = (
            "<h2>Power-domain relations</h2>"
            f"<p class='muted'>Architecture: {html.escape(rel.architecture)} · "
            f"{len(rel.domains)} domains · {n_aon} always-on · {n_sw} "
            f"switchable · {len(rel.relations)} relations. Supply sharing is "
            f"NOT a domain interaction.</p>"
            + (f"<h3>Domain relation matrix</h3><table>{matrix_rows}</table>"
               if matrix_rows else "")
            + "<h3>Relations</h3><table><thead><tr><th>From → To</th>"
            + "<th>Kinds</th><th>Evidence</th></tr></thead><tbody>"
            + relations_rows + "</tbody></table>"
            + (f"<h3>Supply network</h3><table><thead><tr><th>Supply</th>"
               f"<th>Domains</th></tr></thead><tbody>{supply_rows}</tbody>"
               f"</table>" if supply_rows else "")
            + (f"<h3>Domain ownership</h3><table><thead><tr><th>Domain</th>"
               f"<th>Scope</th><th>UPF file</th></tr></thead><tbody>{hier_rows}"
               f"</tbody></table>" if hier_rows else ""))

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
<h1>UPF-Insight - power-intent validation report</h1>
<p class="muted">Files: {result.file_count} · Commands: {result.command_count} ·
Summary: {result.check.error_count} error(s), {result.check.warning_count}
warning(s), {result.check.info_count} info(s)</p>
{readiness_html}
{support_html}
{relations_html}
<h2>Findings</h2>
<table><thead><tr><th>Rule</th><th>Severity</th><th>Location</th>
<th>Message</th><th>Support</th></tr></thead>
<tbody>{findings_html}</tbody></table>
</body></html>"""


__all__ = ["format_text", "format_json", "format_junit", "format_html"]