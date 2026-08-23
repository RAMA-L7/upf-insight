"""UPF-Insight Workspace — Streamlit replica of the vanilla-JS web UI
served by `upf-insight web` (upf_insight/workspace/webui).

Run:
    streamlit run streamlit_app.py

Same page map as the original shell (pages.js):
  WORKSPACE  home · new_analysis
  CORE       validator · generator
  ANALYZE    pst · supply · strategies · relations · design · coverage · readiness
  ADVANCED   diff · gate · test_drive
  OUTPUT     reports · rules · trust · documentation
  RESULTS    overview · support · export

Pure UI on top of the public engine API — no engine code is modified.
"""

from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upf_insight import __version__
from upf_insight.engine.engine import validate
from upf_insight.report.reporter import (
    format_html, format_json, format_junit, format_text,
)
from upf_insight.engine.rules.rules_registry import registered_rules

EXAMPLES_DIR = ROOT / "tests" / "examples"

# ── theme constants (mirror _DESIGN in api_server.py) ────────────
SEV_LABEL = {"fatal": "FATAL", "error": "ERROR", "warning": "WARNING", "info": "INFO"}
TRUST_LABEL = {
    "VALIDATED": ("VALIDATED", "green"),
    "PARTIALLY_VALIDATED": ("PARTIAL", "orange"),
    "NETLIST_REQUIRED": ("NETLIST", "blue"),
    "TCL_EXECUTION_REQUIRED": ("TCL EXEC", "gray"),
    "UNSUPPORTED": ("UNSUPPORTED", "red"),
    "NOT_VALIDATED": ("NOT CHECKED", "gray"),
}
READY_LABEL = {
    "READY": ("READY", "green"),
    "READY_WITH_ADVISORIES": ("READY+", "green"),
    "REVIEW_REQUIRED": ("REVIEW", "orange"),
    "BLOCKED": ("BLOCKED", "red"),
    "INSUFFICIENT_CONTEXT": ("LIMITED", "gray"),
    "NOT_APPLICABLE": ("N/A", "gray"),
}
GROUP_ORDER = ["WORKSPACE", "CORE", "ANALYZE", "ADVANCED", "OUTPUT", "RESULTS"]

st.set_page_config(page_title="UPF-Insight", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")

# ═══════════════════════ helpers ═══════════════════════

def badge(status: str) -> str:
    label, color = READY_LABEL.get(status, (status or "-", "gray"))
    return f":{color}[{label}]"


def trust_badge(status: str) -> str:
    label, color = TRUST_LABEL.get(status, (status or "-", "gray"))
    return f":{color}[{label}]"


def metric_strip(items: list[tuple[str, object]]):
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)


def rows_from(objs, fields: list[str]) -> pd.DataFrame:
    out = []
    for o in objs:
        row = {}
        for f in fields:
            v = getattr(o, f, None)
            if isinstance(v, (list, dict, set)):
                v = ", ".join(str(x) for x in v) if not isinstance(v, dict) else json.dumps(v)
            row[f] = v if v not in ("", None) else "-"
        out.append(row)
    return pd.DataFrame(out)


def run_engine(text: str, name: str = "<session>.upf"):
    with tempfile.NamedTemporaryFile("w", suffix=".upf", delete=False,
                                     encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        tmp = fh.name
    try:
        return validate([tmp])
    finally:
        Path(tmp).unlink(missing_ok=True)


def get_analysis():
    a = st.session_state.get("analysis")
    if a:
        return a["result"], a["name"]
    return None, None


def require_analysis():
    result, name = get_analysis()
    if result is None:
        st.info("No analysis loaded — open **New Analysis** to validate a UPF file first.")
        return None, None
    st.caption(f"Session: `{name}` · {result.command_count} commands · "
               f"readiness {badge(result.readiness.overall)}")
    return result, name


# ═══════════════════════ source picker (New Analysis) ═══════════════════════

def analyze_and_store(text: str, name: str):
    with st.spinner("Running deterministic validation…"):
        result = run_engine(text, name)
    st.session_state["analysis"] = {"result": result, "name": name}
    counts = result.check.to_dict()["counts"]
    st.toast(f"Analysis complete — {counts['errors']} errors, "
             f"{counts['warnings']} warnings", icon="⚡")


def page_new_analysis():
    st.subheader("New Analysis")
    tab_paste, tab_upload, tab_sample = st.tabs(["✍️ Paste", "📤 Upload", "📚 Samples"])
    text, name = None, None
    with tab_paste:
        t = st.text_area("UPF / Tcl content", height=260,
                         placeholder="create_power_domain PD_TOP …", key="na_paste")
        if t.strip():
            text, name = t, "<pasted>.upf"
    with tab_upload:
        up = st.file_uploader("UPF file", type=["upf", "tcl"], key="na_up")
        if up and st.button("Analyze upload", type="primary"):
            analyze_and_store(up.getvalue().decode("utf-8", errors="replace"), up.name)
            st.rerun()
    with tab_sample:
        samples = sorted(p.name for p in EXAMPLES_DIR.glob("*.upf")) \
            if EXAMPLES_DIR.exists() else []
        if not samples:
            st.caption("no fixtures found in tests/examples/")
        else:
            pick = st.selectbox("Known-good / known-bad fixtures", samples)
            if st.button("Load & analyze sample", type="primary"):
                analyze_and_store(
                    (EXAMPLES_DIR / pick).read_text(encoding="utf-8", errors="replace"),
                    pick)
                st.rerun()
    if text:
        if st.button("▶ Analyze pasted UPF", type="primary"):
            analyze_and_store(text, name)
            st.rerun()


# ═══════════════════════ WORKSPACE ═══════════════════════

def page_home():
    st.subheader("◈ Home")
    result, name = get_analysis()
    if result is None:
        st.markdown("Welcome to **UPF-Insight** — deterministic power-intent "
                    "intelligence for IEEE 1801 (UPF).")
        c1, c2 = st.columns(2)
        if c1.button("＋ Start a New Analysis", type="primary"):
            st.session_state["view"] = "new_analysis"
            st.rerun()
        if c2.button("☰ Browse Rule Registry"):
            st.session_state["view"] = "rules"
            st.rerun()
        st.divider()
        st.markdown("**Engine contract** — every finding traces to a line · "
                    "explicit trust boundaries · no LLM in the analysis path.")
        return
    m = result.check.model
    cd = result.check.to_dict()
    cov = result.coverage.to_dict()
    metric_strip([
        ("Errors", cd["counts"]["errors"]),
        ("Warnings", cd["counts"]["warnings"]),
        ("Advisories", cd["counts"]["infos"]),
        ("Domains", len(m.domains)),
        ("Supplies", len(cov.get("declared_supplies", []))),
        ("PST states", sum(p.state_count for p in m.psts.values())),
    ])
    st.divider()
    st.markdown("**Quick actions**")
    qa = [
        ("◈ Validate current UPF", "validator"), ("❐ Generate UPF", "generator"),
        ("⇄ Compare UPF (Diff)", "diff"), ("⌦ Run CI Gate", "gate"),
        ("⇩ Export JSON", "export"), ("❐ Generate Report", "reports"),
        ("▶ Test Drive", "test_drive"), ("◫ Open Power States", "pst"),
        ("▤ Open Supply Network", "supply"), ("⇄ Open Strategies", "strategies"),
        ("◉ Open Domain Relations", "relations"), ("▦ Open Coverage", "coverage"),
        ("◫ Open Health (Readiness)", "readiness"), ("☰ Rules Registry", "rules"),
        ("◆ Trust Model", "trust"),
    ]
    per_row = 3
    for i in range(0, len(qa), per_row):
        cols = st.columns(per_row)
        for col, (label, view) in zip(cols, qa[i:i + per_row]):
            if col.button(label, use_container_width=True, key=f"qa_{view}"):
                st.session_state["view"] = view
                st.rerun()


# ═══════════════════════ CORE ═══════════════════════

def page_validator():
    st.subheader("◈ Validation")
    result, name = require_analysis()
    if result is None:
        return
    cd = result.check.to_dict()
    counts = cd["counts"]
    metric_strip([("Errors", counts["errors"]), ("Warnings", counts["warnings"]),
                  ("Info", counts["infos"]), ("Commands", result.command_count)])

    findings = cd["findings"]
    sev_f = st.selectbox("Severity", ["All", "error", "warning", "info"])
    rules_avail = sorted({f["rule"] for f in findings})
    rule_f = st.selectbox("Rule", ["All"] + rules_avail)
    q = st.text_input("Filter findings", placeholder="substring…").lower()

    rows = [f for f in findings
            if (sev_f == "All" or f["severity"] == sev_f)
            and (rule_f == "All" or f["rule"] == rule_f)
            and (not q or q in str(f).lower())]
    if rows:
        df = pd.DataFrame([{
            "Severity": SEV_LABEL.get(f["severity"], f["severity"]).upper(),
            "Rule": f["rule"], "Finding": f["message"],
            "Subject": f.get("subject") or "-",
            "File": f.get("file") or "-", "Loc": f"L{f['line']}" if f.get("line") else "-",
            "Support": f.get("support") or "-",
        } for f in rows])
        st.dataframe(df, use_container_width=True, height=420)
    else:
        st.success("No findings match this filter." if findings else
                   "Clean — no findings at this trust level.")


def page_generator():
    st.subheader("❐ Generator")
    d1, d2, d3 = st.columns(3)
    design_top = d1.text_input("Design top", value="TOP", key="g_top")
    upf_version = d2.selectbox("UPF version", ["2.1", "3.0", "4.0"], index=1)
    architecture = d3.selectbox("Architecture", ["flat", "hierarchical"])
    v1, v2, v3 = st.columns(3)
    primary_power = v1.text_input("Primary power net", value="vdd", key="g_pwr")
    primary_ground = v2.text_input("Primary ground net", value="vss", key="g_gnd")
    on_voltage = v3.text_input("ON voltage", value="0.85", key="g_v")
    domains_raw = st.text_input("Power domains (comma-separated)",
                                value="PD_TOP, PD_CORE, PD_SRAM, PD_GPU", key="g_dom")
    doms = [d.strip() for d in domains_raw.split(",") if d.strip()]
    iso_domains = st.multiselect("Isolation on domains", doms)
    ret_domains = st.multiselect("Retention on domains", doms)
    sw_domains = st.multiselect("Switchable domains (power switches)", doms)
    sw_in = sw_out = sw_ctrl = ""
    if sw_domains:
        s1, s2, s3 = st.columns(3)
        sw_in = s1.text_input("Switch input supply port", value="vdd_sw_in", key="g_swin")
        sw_out = s2.text_input("Switch output net", value="vdd_sw_out", key="g_swout")
        sw_ctrl = s3.text_input("Switch control port", value="pwr_en", key="g_swctrl")
    ls_domains = st.multiselect("Level shifters on domains", doms)

    if st.button("▶ Generate UPF skeleton", type="primary"):
        from upf_insight.generate.generator import (
            DomainParam, IsolationParam, LevelShifterParam, RetentionParam,
            SwitchParam, UPFParams, generate_upf,
        )
        params = UPFParams(
            design_top=design_top, upf_version=upf_version,
            primary_power=primary_power, primary_ground=primary_ground,
            on_voltage=on_voltage,
            domains=[DomainParam(d) for d in doms],
            isolation=[IsolationParam(d) for d in iso_domains],
            retention=[RetentionParam(d) for d in ret_domains],
            switches=[SwitchParam(
                name=f"sw_{d.lower()}", domain=d,
                input_supply=sw_in or "vdd_sw_in",
                output_supply=sw_out or "vdd_sw_out",
                control_port=sw_ctrl or "pwr_en",
            ) for d in sw_domains],
            level_shifters=[LevelShifterParam(d) for d in ls_domains],
            architecture=architecture,
        )
        try:
            out = generate_upf(params)
        except ValueError as exc:
            st.error(f"generate: {exc}")
            return
        st.code(out, language="tcl")
        st.download_button("Download UPF", out, file_name=f"{design_top.lower()}.upf",
                           mime="text/plain")
        res = run_engine(out)
        cd = res.check.to_dict()["counts"]
        st.markdown(f"**Self-check:** {cd['errors']} error(s), {cd['warnings']} warning(s) "
                    f"on generated output.")


# ═══════════════════════ ANALYZE ═══════════════════════

def page_pst():
    st.subheader("◫ Power States")
    result, _ = require_analysis()
    if result is None:
        return
    m = result.check.model
    if not m.psts:
        st.warning("No Power State Table declared (UPF-032 territory).")
        return
    for pname, p in sorted(m.psts.items()):
        a = result.pst.to_dict() if hasattr(result.pst, "to_dict") else {}
        metric_strip([
            ("PST", pname), ("States", getattr(p, "state_count", a.get("state_count", 0))),
            ("Declared", len(a.get("declared_supply_states", []))),
            ("Used", len(a.get("used_supply_states", []))),
            ("Unused", len(a.get("unused_states", []))),
            ("Undeclared", len(a.get("undeclared_states", []))),
        ])
        trans = a.get("transitions") or []
        st.markdown("**Transitions**")
        st.dataframe(pd.DataFrame(trans), use_container_width=True) if trans \
            else st.caption("none recorded")
        for label, key in [("Unused declared states", "unused_states"),
                           ("Undeclared references", "undeclared_states"),
                           ("Cross-state events", "cross_state_events")]:
            items = a.get(key) or []
            if items:
                st.warning(f"{label}: {json.dumps(items, default=str)}")
        if a.get("coverage_note"):
            st.info(a["coverage_note"])


def page_supply():
    st.subheader("▤ Supply Network")
    result, _ = require_analysis()
    if result is None:
        return
    m = result.check.model
    metric_strip([
        ("Domains", len(m.domains)), ("Supply ports", len(m.supply_ports)),
        ("Supply nets", len(m.supply_nets)), ("Supply sets", len(m.supply_sets)),
        ("Switches", len(getattr(m, "switches", {}) or {})),
    ])
    st.markdown("**Power domains**")
    st.dataframe(rows_from(m.domains.values(),
                           ["name", "scope", "elements", "primary_supply_sets",
                            "declared_line"]), use_container_width=True)
    if m.supply_nets:
        st.markdown("**Supply nets**")
        st.dataframe(rows_from(m.supply_nets.values(),
                               ["name", "connected_to", "declared_line"]),
                     use_container_width=True)
    if m.supply_ports:
        st.markdown("**Supply ports**")
        st.dataframe(rows_from(m.supply_ports.values(),
                               ["name", "direction", "declared_line"]),
                     use_container_width=True)
    if m.supply_sets:
        st.markdown("**Supply sets**")
        st.dataframe(rows_from(m.supply_sets.values(), ["name", "functions",
                                                        "declared_line"]),
                     use_container_width=True)


def page_strategies():
    st.subheader("⇄ Strategies")
    result, _ = require_analysis()
    if result is None:
        return
    m = result.check.model
    metric_strip([
        ("Isolation", len(m.isolation)), ("Level shifters", len(m.level_shifters)),
        ("Retention", len(m.retentions)),
        ("Repeaters", len(getattr(m, "repeaters", []) or [])),
    ])
    if m.isolation:
        st.markdown("**Isolation**")
        st.dataframe(rows_from(m.isolation,
                               ["domain", "elements", "clamp_value", "location",
                                "isolation_supply", "control_signal", "applies_to",
                                "declared_line"]), use_container_width=True)
    if m.level_shifters:
        st.markdown("**Level shifters**")
        st.dataframe(rows_from(m.level_shifters,
                               ["domain", "location", "threshold", "declared_line"]),
                     use_container_width=True)
    if m.retentions:
        st.markdown("**Retention**")
        st.dataframe(rows_from(m.retentions,
                               ["domain", "retention_supply", "save_signal",
                                "restore_signal", "declared_line"]),
                     use_container_width=True)
    if not (m.isolation or m.level_shifters or m.retentions):
        st.caption("No power strategies declared.")


def page_relations():
    st.subheader("◉ Domain Relations")
    result, _ = require_analysis()
    if result is None:
        return
    rel = result.relations
    if rel is None:
        st.info("No relation data available.")
        return
    rd = rel.to_dict()
    doms = rel.domains
    metric_strip([
        ("Architecture", rel.architecture.title()), ("Domains", len(doms)),
        ("Always-on", sum(1 for d in doms if d.type == "ALWAYS_ON")),
        ("Switchable", sum(1 for d in doms if d.type == "SWITCHABLE")),
        ("Relations", len(rel.relations)),
    ])
    if rel.relations:
        st.markdown("**Domain relations**")
        st.dataframe(pd.DataFrame([{
            "From": r.from_domain, "To": r.to_domain, "Label": r.label,
        } for r in rel.relations]), use_container_width=True)
    names = [d.name for d in doms]
    if names:
        st.markdown("**Matrix**")
        matrix = pd.DataFrame(
            [[rel.matrix.get(f, {}).get(t, "-") for t in names] for f in names],
            index=names, columns=names)
        st.dataframe(matrix, use_container_width=True)


def page_design():
    st.subheader("▤ Design")
    result, _ = require_analysis()
    if result is None:
        return
    m = result.check.model
    st.markdown(f"Design top: `{m.design_top or '-'}` · scope: `{m.current_scope}`")
    st.info("Design-aware rules (UPF-080..084) need a netlist/RTL context snapshot; "
            "without it these stay NETLIST_REQUIRED.")
    if m.library_mappings:
        st.markdown("**Library PG mappings**")
        st.dataframe(pd.DataFrame(m.library_mappings), use_container_width=True)
    if m.port_attributes:
        st.markdown("**Port attributes**")
        st.dataframe(pd.DataFrame(
            [{"port": k, **(v if isinstance(v, dict) else {"value": v})}
             for k, v in m.port_attributes.items()]), use_container_width=True)


def page_coverage():
    st.subheader("▦ Coverage")
    result, _ = require_analysis()
    if result is None:
        return
    cov = result.coverage.to_dict()
    metric_strip([
        ("Domain coverage", f"{round((cov.get('domain_coverage') or 0) * 100)}%"),
        ("Supply coverage", f"{round((cov.get('supply_coverage') or 0) * 100)}%"),
        ("Unreferenced supplies", len(cov.get("unreferenced_supplies", []))),
        ("Declared supplies", len(cov.get("declared_supplies", []))),
    ])
    dom_rows = [d for d in (cov.get("domains") or [])
                if isinstance(d, dict)] or [
        {"domain": str(d), "covered": "?"} for d in (cov.get("domains") or [])]
    if dom_rows:
        st.markdown("**Domains**")
        st.dataframe(pd.DataFrame(dom_rows), use_container_width=True)
    unref = cov.get("unreferenced_supplies") or []
    if unref:
        st.warning(f"Unreferenced supplies: {', '.join(map(str, unref))}")


def page_readiness():
    st.subheader("◫ Health (Readiness)")
    result, _ = require_analysis()
    if result is None:
        return
    ready = result.readiness
    st.markdown(f"### Overall: {badge(ready.overall)} · mode `{ready.mode}`")
    dims = ready.dimensions or {}
    for dim in dims.values():
        _, color = READY_LABEL.get(dim.status, (dim.status, "gray"))
        with st.expander(f"{dim.dimension} — :{color}[{dim.status}]  \n{dim.summary}"):
            if dim.findings:
                st.dataframe(pd.DataFrame([{
                    "Code": f.code, "Sev": f.severity.upper(), "Line": f.line or "-",
                    "Tier": f.tier, "Message": f.message,
                } for f in dim.findings]), use_container_width=True)
            else:
                st.caption("no findings in this dimension")
    if ready.blockers:
        st.error(f"Blockers: {len(ready.blockers)}")
        st.dataframe(pd.DataFrame(ready.blockers), use_container_width=True)
    if ready.review_items:
        st.warning(f"Review items: {len(ready.review_items)}")
        st.dataframe(pd.DataFrame(ready.review_items), use_container_width=True)
    if ready.advisories:
        st.info(f"Advisories: {len(ready.advisories)}")
        st.dataframe(pd.DataFrame(ready.advisories), use_container_width=True)


# ═══════════════════════ ADVANCED ═══════════════════════

def page_diff():
    st.subheader("⇄ UPF Diff")
    c_old, c_new = st.columns(2)
    old_up = c_old.file_uploader("Version A (old)", type=["upf", "tcl"], key="df_old")
    new_up = c_new.file_uploader("Version B (new)", type=["upf", "tcl"], key="df_new")
    if old_up and new_up and st.button("▶ Semantic diff", type="primary"):
        from upf_insight.diff.differ import diff_files
        tmpdir = Path(tempfile.mkdtemp())
        p_old, p_new = tmpdir / old_up.name, tmpdir / new_up.name
        p_old.write_bytes(old_up.getvalue())
        p_new.write_bytes(new_up.getvalue())
        changes = diff_files(str(p_old), str(p_new))
        st.session_state["diff_changes"] = [{
            "Kind": getattr(ch, "kind", getattr(ch, "change_type", "?")),
            "What": getattr(ch, "what", getattr(ch, "entity", "")),
            "Object": getattr(ch, "object", ""),
            "Detail": getattr(ch, "detail", getattr(ch, "description", "")),
        } for ch in changes]
    changes = st.session_state.get("diff_changes")
    if changes is not None:
        metric_strip([("Semantic changes A→B", len(changes))])
        if changes:
            st.dataframe(pd.DataFrame(changes), use_container_width=True, height=380)
        else:
            st.success("No semantic differences.")
        st.download_button("Download diff JSON", json.dumps(changes, indent=2),
                           file_name="upf-diff.json", mime="application/json")


GATE_POLICIES = ["BLOCKERS_ONLY", "NO_READINESS_REGRESSION", "STRICT"]

def page_gate():
    st.subheader("⌦ CI Gate")
    result, name = require_analysis()
    if result is None:
        return
    policy = st.selectbox("Gate policy", GATE_POLICIES + ["CUSTOM (severity cap)"])
    custom_cap = None
    if policy.startswith("CUSTOM"):
        custom_cap = st.select_slider("Fail at or above severity",
                                      options=["info", "warning", "error"])
    cd = result.check.to_dict()
    counts = cd["counts"]
    blockers = ready_blockers = 0
    ready = result.readiness
    if policy == "BLOCKERS_ONLY":
        failed = bool(ready.blockers) or counts["errors"] > 0
    elif policy == "STRICT":
        failed = counts["errors"] + counts["warnings"] > 0
    elif policy == "NO_READINESS_REGRESSION":
        failed = ready.overall in ("BLOCKED", "REVIEW_REQUIRED")
    else:
        rank = {"info": 0, "warning": 1, "error": 2, "fatal": 3}
        failed = any(rank.get(f["severity"], 0) >= rank[custom_cap]
                     for f in cd["findings"])
    exit_code = 1 if failed else 0
    st.markdown("---")
    verdict = ":red[FAIL]" if failed else ":green[PASS]"
    st.markdown(f"# Gate verdict: {verdict}  ·  exit `{exit_code}`")
    metric_strip([
        ("Errors", counts["errors"]), ("Warnings", counts["warnings"]),
        ("Infos", counts["infos"]), ("Readiness", ready.overall),
        ("Policy", policy),
    ])
    st.caption("Exit-code contract: 0 pass · 1 gate failed · 2 invalid invocation · "
               "3 engine failure")


def page_test_drive():
    st.subheader("▶ Test Drive")
    st.markdown("Guided walkthrough of the engine on bundled fixtures.")
    samples = sorted(p.name for p in EXAMPLES_DIR.glob("*.upf")) \
        if EXAMPLES_DIR.exists() else []
    if not samples:
        st.warning("No fixtures found.")
        return
    steps_done = st.session_state.setdefault("drive_steps", {})
    for i, s in enumerate(samples[:4], 1):
        c1, c2 = st.columns([3, 1])
        c1.write(f"`{s}`")
        if c2.button(f"Run step {i}", key=f"td_{s}"):
            text = (EXAMPLES_DIR / s).read_text(encoding="utf-8", errors="replace")
            analyze_and_store(text, s)
            steps_done[s] = True
            st.rerun()
        if steps_done.get(s):
            res = st.session_state.get("analysis")
            if res and res["name"] == s:
                counts = res["result"].check.to_dict()["counts"]
                c2.caption(f"✓ {counts['errors']}e/{counts['warnings']}w")
    st.divider()
    if st.session_state.get("analysis"):
        st.success(f'Current session: `{st.session_state["analysis"]["name"]}` '
                   f"— explore it under ANALYZE / RESULTS.")


# ═══════════════════════ OUTPUT ═══════════════════════

def page_reports():
    st.subheader("❐ Reports")
    result, name = require_analysis()
    if result is None:
        return
    view = st.radio("Format", ["HTML", "Text", "JSON", "JUnit XML"], horizontal=True)
    if view == "HTML":
        st.components.v1.html(format_html(result), height=560, scrolling=True)
        body, ext, mime = format_html(result), "html", "text/html"
    elif view == "Text":
        st.code(format_text(result), language="text")
        body, ext, mime = format_text(result), "txt", "text/plain"
    elif view == "JSON":
        st.code(format_json(result), language="json")
        body, ext, mime = format_json(result), "json", "application/json"
    else:
        body = format_junit(result)
        st.code(body, language="xml")
        ext, mime = "xml", "application/xml"
    st.download_button(f"Download .{ext}", body,
                       file_name=f"{Path(name).stem}.{ext}", mime=mime)


def page_rules():
    st.subheader("☰ Rules Registry")
    rules = registered_rules()
    metric_strip([("Total", len(rules)),
                  ("Errors", sum(1 for r in rules if r.severity == "error")),
                  ("Warnings", sum(1 for r in rules if r.severity == "warning")),
                  ("Infos", sum(1 for r in rules if r.severity == "info"))])
    l1, l2, l3 = st.columns([2, 1, 1])
    q = l1.text_input("Search", placeholder="e.g. UPF-04, isolation", key="rules_q").lower()
    layer_f = l2.selectbox("Layer", ["All"] + sorted({r.layer for r in rules}))
    sev_f = l3.selectbox("Severity", ["All", "error", "warning", "info"])
    df = pd.DataFrame([{
        "Code": r.code, "Severity": r.severity.upper(), "Layer": r.layer,
        "Title": r.title,
        "Depends on": ", ".join(r.depends_on or []) or "-",
    } for r in rules])
    if q:
        df = df[df.apply(lambda row: row.astype(str).str.lower().str.contains(q).any(),
                         axis=1)]
    if layer_f != "All":
        df = df[df.Layer == layer_f]
    if sev_f != "All":
        df = df[df.Severity == sev_f.upper()]
    st.dataframe(df, use_container_width=True, height=480)


def page_trust():
    st.subheader("◆ Trust Model")
    result, _ = require_analysis()
    if result is None:
        return
    sup = result.support.to_dict()
    statuses = sup.get("statuses", {})
    chips = "  ".join(trust_badge(k) + f" × {v}" for k, v in statuses.items())
    st.markdown(chips)
    notes = sup.get("notes") or []
    if notes:
        st.markdown("**Notes**")
        for n in notes:
            st.caption(f"— {n}")
    st.info("Trust statuses tell you how much evidence backs each result: "
            "VALIDATED (full command stream) → PARTIAL → NETLIST_REQUIRED / "
            "TCL_EXECUTION_REQUIRED → UNSUPPORTED. \"No errors\" never means "
            "\"power proven correct\".")


def page_documentation():
    st.subheader("❐ Documentation")
    st.markdown(f"""#### UPF-Insight `{__version__}` — command surface

| Command | Purpose |
|---|---|
| `check` | validate UPF files (`--format text\\|json\\|junit`, `--baseline`, `--gate`) |
| `model` | dump the power-intent model as JSON |
| `pst` | Power State Table analysis |
| `coverage` | structural domain/supply coverage |
| `report` | human-readable HTML/text/json report |
| `diff` | semantic UPF diff between two versions |
| `generate` | scaffold standard UPF constructs |
| `rules` | list/audit the registry |
| `web` | this workspace (vanilla JS or Streamlit) |

**Exit-code contract:** 0 pass · 1 gate failed · 2 invalid invocation · 3 engine failure.

Deterministic engine — same input, same verdict. No EDA tool required,
no LLM in the analysis path.""")


# ═══════════════════════ RESULTS ═══════════════════════

def page_overview():
    st.subheader("Summary")
    result, name = require_analysis()
    if result is None:
        return
    m = result.check.model
    cd = result.check.to_dict()
    cov = result.coverage.to_dict()
    metric_strip([
        ("File", name), ("Commands", result.command_count),
        ("Errors", cd["counts"]["errors"]), ("Warnings", cd["counts"]["warnings"]),
        ("Readiness", result.readiness.overall),
        ("Trust", max(cd.get("support_boundary", {}).values(), default="-")
         if isinstance(cd.get("support_boundary"), dict) else "-"),
    ])
    st.markdown("**Model at a glance**")
    st.dataframe(pd.DataFrame([
        ("Domains", len(m.domains)), ("Supply nets", len(m.supply_nets)),
        ("Supply ports", len(m.supply_ports)), ("Supply sets", len(m.supply_sets)),
        ("Isolation strategies", len(m.isolation)),
        ("Level shifters", len(m.level_shifters)),
        ("Retention strategies", len(m.retentions)),
        ("PSTs", len(m.psts)),
        ("Domain coverage", f"{round((cov.get('domain_coverage') or 0)*100)}%"),
        ("Supply coverage", f"{round((cov.get('supply_coverage') or 0)*100)}%"),
    ], columns=["Aspect", "Value"]).astype({"Value": str}), use_container_width=True)


def page_support():
    st.subheader("◇ Support Boundary")
    result, _ = require_analysis()
    if result is None:
        return
    sup = result.support.to_dict()
    st.markdown("**Status distribution**")
    st.dataframe(pd.DataFrame(
        [{"Status": k, "Label": TRUST_LABEL.get(k, (k, ""))[0], "Count": v}
         for k, v in (sup.get("statuses") or {}).items()]), use_container_width=True)
    notes = sup.get("notes") or []
    if notes:
        st.markdown("**Engine notes**")
        for n in notes:
            st.caption(f"— {n}")
    st.info("Every result carries an explicit trust boundary. Findings marked "
            "PARTIAL ran with reduced evidence; UNSUPPORTED constructs are reported "
            "rather than silently ignored.")


def page_export():
    st.subheader("⇩ Export")
    result, name = require_analysis()
    if result is None:
        return
    stem = Path(name).stem or "analysis"
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("JSON report", format_json(result),
                       file_name=f"{stem}.report.json", mime="application/json",
                       use_container_width=True)
    c2.download_button("Text report", format_text(result),
                       file_name=f"{stem}.report.txt", mime="text/plain",
                       use_container_width=True)
    c3.download_button("JUnit XML", format_junit(result),
                       file_name=f"{stem}.junit.xml", mime="application/xml",
                       use_container_width=True)
    c4.download_button("HTML report", format_html(result),
                       file_name=f"{stem}.report.html", mime="text/html",
                       use_container_width=True)
    # raw model dump (mirrors CLI `model`)
    m = result.check.model
    dump = {}
    for attr in ("domains", "supply_nets", "supply_ports", "supply_sets"):
        obj = getattr(m, attr, {})
        dump[attr] = {
            k: {f.name: _plainify(getattr(v, f.name))
                for f in dataclasses.fields(v)}
            for k, v in obj.items()
        } if obj else {}
    st.download_button("Model JSON (CLI `model` equivalent)", json.dumps(dump, indent=2),
                       file_name=f"{stem}.model.json", mime="application/json")


def _plainify(v):
    if isinstance(v, (list, tuple, set)):
        return [_plainify(x) for x in v]
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return {f.name: _plainify(getattr(v, f.name)) for f in dataclasses.fields(v)}
    return v


# ═══════════════════════ shell ═══════════════════════

PAGES = {
    "home":          ("Home", page_home, "WORKSPACE", "◈"),
    "new_analysis":  ("New Analysis", page_new_analysis, "WORKSPACE", "＋"),
    "validator":     ("Validation", page_validator, "CORE", "◈"),
    "generator":     ("Generator", page_generator, "CORE", "❐"),
    "pst":           ("Power States", page_pst, "ANALYZE", "◫"),
    "supply":        ("Supply Network", page_supply, "ANALYZE", "▤"),
    "strategies":    ("Strategies", page_strategies, "ANALYZE", "⇄"),
    "relations":     ("Domain Relations", page_relations, "ANALYZE", "◉"),
    "design":        ("Design", page_design, "ANALYZE", "▤"),
    "coverage":      ("Coverage", page_coverage, "ANALYZE", "▦"),
    "readiness":     ("Health", page_readiness, "ANALYZE", "◫"),
    "diff":          ("UPF Diff", page_diff, "ADVANCED", "⇄"),
    "gate":          ("CI Gate", page_gate, "ADVANCED", "⌦"),
    "test_drive":    ("Test Drive", page_test_drive, "ADVANCED", "▶"),
    "reports":       ("Reports", page_reports, "OUTPUT", "❐"),
    "rules":         ("Rules", page_rules, "OUTPUT", "☰"),
    "trust":         ("Trust", page_trust, "OUTPUT", "◆"),
    "documentation": ("Documentation", page_documentation, "OUTPUT", "❐"),
    "overview":      ("Summary", page_overview, "RESULTS", "◈"),
    "support":       ("Support", page_support, "RESULTS", "◇"),
    "export":        ("Export", page_export, "RESULTS", "⇩"),
}

with st.sidebar:
    st.markdown(f"# ⚡ UPF<b>-Insight</b> `{__version__}`", unsafe_allow_html=True)
    st.caption("power-intent validator · deterministic · offline · no LLM")
    current = st.session_state.get("view", "home")
    for group in GROUP_ORDER:
        items = [(vid, meta) for vid, meta in PAGES.items() if meta[2] == group]
        if not items:
            continue
        st.markdown(f"**:small[{group}]**")
        for vid, (label, _, _, icon) in items:
            if st.button(f"{icon}  {label}", key=f"nav_{vid}",
                         use_container_width=True,
                         type="primary" if vid == current else "secondary"):
                st.session_state["view"] = vid
                st.rerun()
    st.divider()
    a = st.session_state.get("analysis")
    if a:
        st.caption(f"session: `{a['name']}`")
    else:
        st.caption("no analysis loaded")

PAGES[current][1]()
