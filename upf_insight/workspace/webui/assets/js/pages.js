/* ═══════════════════════════════════════════════════════════════════════════
   UPF-Insight - pages.js
   All workspace page renderers. Every page consumes REAL backend evidence
   through the API - no mock data, no invented counts. All user-controlled
   content is escaped via theme.esc. Mirrors the Ṛta pages.js structure.
   ═══════════════════════════════════════════════════════════════════════════ */

import { esc, statusBadge, severityClass } from "./theme.js";
import { pageHead, sectionTitle, metricRow, chips, emptyState, typedError,
         callout, sourceViewer, sourceExcerpt, table, accordion, kvList,
         segFilter, findingRow, escAttr } from "./components.js";
import { readinessRail, supplyStripHtml, pstMatrixHtml } from "./viz.js";
import { RULE_FIXES } from "./rule_fixes.js";

export const App = {
  state: {
    analysis: null,
    upf: "",
    filename: "pasted.upf",
    filters: { sev: "All", rule: "All", q: "" },
    inspector: null,
    rules: null,
    session: {
      id: null, name: "Untitled session", status: "EMPTY", createdAt: null,
      upf: "", netlist: "", filename: "pasted.upf", analysis: null,
    },
    recentSessions: [],
    ruleFilter: "All",
    // Feature-local input surfaces (standalone tools never depend on a session).
    diffA: "", diffB: "", diffFileA: "pasted_a.upf", diffFileB: "pasted_b.upf",
    gateUpf: "", reportUpf: "",
  },
};

export async function fetchSample(name) {
  const r = await fetch(`/api/sample?name=${encodeURIComponent(name)}`);
  if (!r.ok) throw new Error(`sample ${name} unavailable (HTTP ${r.status})`);
  const j = await r.json();
  return j.content || "";
}

async function post(path, body) {
  const r = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail || detail; } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return r.json();
}
async function get(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export function toast(msg, isErr = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 2600);
}

export function openInspector(title, html) {
  App.state.inspector = { title, html };
  document.getElementById("inspector-title").textContent = title;
  document.getElementById("inspector-body").innerHTML = html;
  document.getElementById("inspector").classList.add("open");
  document.getElementById("inspector").setAttribute("aria-hidden", "false");
  document.getElementById("inspector-backdrop").hidden = false;
}
export function closeInspector() {
  document.getElementById("inspector").classList.remove("open");
  document.getElementById("inspector").setAttribute("aria-hidden", "true");
  document.getElementById("inspector-backdrop").hidden = true;
  App.state.inspector = null;
}

/* ── Shared: finding helpers (UPF findings carry rule/file/line) ────────── */
function findingObj(it) { return it.file || ""; }
function findingLoc(it) { return it.line ? `L${it.line}` : ""; }
function locLines(it) { return it.line ? [it.line] : []; }

/* Derive a trust scope from the support boundary statuses. */
function trustFromSupport(support) {
  if (!support || !support.statuses) return "NOT_VALIDATED";
  const s = support.statuses;
  if (s.NETLIST_REQUIRED) return "NETLIST_REQUIRED";
  if (s.TCL_EXECUTION_REQUIRED) return "TCL_EXECUTION_REQUIRED";
  if (s.UNSUPPORTED) return "UNSUPPORTED";
  if (s.PARTIALLY_VALIDATED) return "PARTIALLY_VALIDATED";
  if (s.VALIDATED) return "VALIDATED";
  return "NOT_VALIDATED";
}

function scopeNote(a) {
  if (!a) return "";
  const c = a.check || {};
  const counts = c.counts || {};
  const m = a.model || {};
  const parts = [
    `${counts.errors ?? 0} errors`, `${counts.warnings ?? 0} warnings`,
    `${Object.keys(m.domains || {}).length} domains`,
    `${Object.keys(m.supply_nets || {}).length + Object.keys(m.supply_sets || {}).length + Object.keys(m.supply_ports || {}).length} supplies`,
    `${(a.pst || {}).state_count ?? 0} PST states`,
  ];
  return parts.join(" · ");
}

/* Every feature owns its input surface - standalone first. When no analysis
   exists yet, the feature page renders its own UPF input + Analyze instead of
   a dead "run a validation first" wall. The same real engine runs either way. */
function standaloneAnalyzeHtml(title, note) {
  return `<div class="input-surface entry">
    <div class="entry-step">
      <div class="es-num">1</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">${esc(title)}</span><span class="es-req">UPF</span></div>
        <p class="es-why">${esc(note)}</p>
        <div class="es-actions">
          <button class="btn btn-sm" id="sa-pick" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="sa-sample" type="button">Load sample</button>
          <button class="btn btn-sm btn-ghost" id="sa-clear" type="button">Clear</button>
          <span class="is-file mono" id="sa-file">${esc(App.state.filename)}</span>
        </div>
        <textarea class="code-input" id="sa-upf" rows="6" spellcheck="false" placeholder="upf_version 3.0&#10;set_design_top top&#10;create_power_domain core -elements {u_core}&#10;...">${esc(App.state.upf)}</textarea>
      </div>
    </div>
    <div class="entry-foot">
      <button class="btn btn-primary" id="sa-analyze" type="button">Analyze</button>
      <span class="mono" style="font-size:11px;color:var(--text-muted)">runs locally · deterministic · offline · no LLM</span>
    </div>
  </div>`;
}

/* ── Overview (Summary) ─────────────────────────────────────────────────── */
export async function pageOverview() {
  const a = App.state.analysis;
  if (!a) {
    return pageHead("RESULTS", "Summary", "Run this tool on your UPF - the summary is built from real analysis evidence.",
      "Provide a UPF below and press Analyze - the summary renders here.")
      + standaloneAnalyzeHtml("Summary", "Drop your IEEE 1801 UPF in here - UPF-Insight analyzes it and renders the executive summary in place.");
  }
  const rdy = a.readiness || {};
  const c = a.check || {};
  const counts = c.counts || {};
  const m = a.model || {};
  const cov = a.coverage || {};
  const blockers = (rdy.blockers || []).slice(0, 8);

  let html = pageHead("RESULTS", "Summary", "The executive view - verdict, trust, power intent, coverage.",
                      "Start with the verdict, then open Findings for the detail.");
  html += `<div class="rdy-overall">
    <div><div class="ro-label">Overall readiness</div><div class="ro-value">${statusBadge("readiness", rdy.overall || "INSUFFICIENT_CONTEXT")}</div></div>
    <div style="margin-left:auto;text-align:right"><div class="ro-label">Mode</div><div class="mono" style="font-size:13px;color:var(--text-secondary)">${esc((rdy.mode || "UPF_ONLY").replace(/_/g, " "))}</div></div>
  </div>`;
  html += readinessRail(rdy);

  html += metricRow([
    { label: "Errors", value: counts.errors ?? 0 }, { label: "Warnings", value: counts.warnings ?? 0 },
    { label: "Advisories", value: counts.infos ?? 0 }, { label: "Domains", value: Object.keys(m.domains || {}).length },
    { label: "Supplies", value: (cov.declared_supplies || []).length },
    { label: "PST states", value: (a.pst || {}).state_count ?? 0 },
  ]);

  html += sectionTitle("Trust / support boundary");
  html += `<div class="chips">${statusBadge("trust", trustFromSupport(a.support))}</div>`;
  const sup = a.support || {};
  html += `<div class="mono" style="font-size:12px;color:var(--text-secondary);margin-top:4px">${esc(JSON.stringify(sup.statuses || {}).replace(/[{}"]/g, ""))}</div>`;

  if (blockers.length) {
    html += sectionTitle(`Blockers (${blockers.length})`);
    html += blockers.map(b => `<div class="ilink"><span class="il-rule">${esc(b.code)}</span><span class="il-kind" style="color:var(--error)">BLOCKER</span><span class="il-a">${esc(b.message)}</span>${b.line ? `<span class="il-loc">L${b.line}</span>` : ""}</div>`).join("");
  }

  html += sectionTitle("Power intent inventory");
  html += `<div class="mono" style="font-size:12px;color:var(--text-secondary)">${scopeNote(a)}</div>`;

  if (cov.domain_coverage !== undefined) {
    html += sectionTitle("Coverage", "what the intent touches - coverage ≠ correctness");
    html += metricRow([
      { label: "Domain coverage", value: Math.round(cov.domain_coverage * 100) + "%" },
      { label: "Supply coverage", value: Math.round(cov.supply_coverage * 100) + "%" },
      { label: "Unreferenced supplies", value: (cov.unreferenced_supplies || []).length },
    ]);
    html += `<p class="callout co-info" style="margin-top:6px"><span><strong>Coverage is not correctness</strong> - a fully covered design can still have power-intent errors.</span></p>`;
  }

  (rdy.notes || []).forEach(n => html += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">- ${esc(n)}</div>`);
  html += `<p class="callout co-warning" style="margin-top:16px"><span><strong>READY ≠ signoff</strong> - this is a power-intent review, not a power/IR signoff.</span></p>`;
  return html + "</div>";
}

/* ── Home dashboard (landing) ───────────────────────────────────────────── */
function capCard(icon, title, desc, input, view, cta) {
  return `<div class="cap-card" tabindex="0" role="button" aria-label="open ${esc(title)}">
    <div class="cap-head"><span class="cap-icon">${icon}</span><span class="cap-title">${esc(title)}</span></div>
    <p class="cap-desc">${esc(desc)}</p>
    <div class="cap-tags">${input ? `<span class="cap-tag mono">${esc(input)}</span>` : `<span class="cap-tag mono">no input required</span>`}</div>
    <div class="cap-cta"><button class="btn" type="button" data-home-view="${esc(view)}">${esc(cta)}<span>→</span></button></div>
  </div>`;
}

const _RULE_COUNT = () => (App.state.rules && App.state.rules.length) || 65;

function capGroup(label, note, cards) {
  return sectionTitle(label, note) + `<div class="caps-grid">${cards.join("")}</div>`;
}

export async function pageHome() {
  const caps = {
    core: [
      capCard("◈", "UPF Validation",
       "Check IEEE 1801 power intent across six analysis layers - every finding traces to a rule and a source line.",
       "UPF required · design JSON optional",
       "validator", "Open Validation"),
      capCard("❐", "UPF Generator",
       "Build power domains, switches, isolation, level shifters, retention and PST states - then validate the emitted UPF in place.",
       "domain / switch / strategy params",
       "generator", "Open Generator"),
    ],
    analyze: [
      capCard("◫", "Power State Intelligence",
       "Declared supply states, the Power State Table, and cross-state legality in one matrix.",
       "create_pst · add_pst_state",
       "pst", "Open Power States"),
      capCard("▤", "Supply Network",
       "Power domains, supply ports/nets/sets, and power switches behind the intent.",
       "create_power_domain · create_supply_*",
       "supply", "Open Supply Network"),
      capCard("⇄", "Strategies",
       "Isolation, retention and level-shifter strategies - location, clamp, control and supply.",
       "set_isolation · set_retention · set_level_shifter",
       "strategies", "Open Strategies"),
      capCard("◉", "Domain Relations",
       "The power-domain relation matrix - which domains interact, switch boundaries, level-shift crossings, and the evidence behind each cell.",
       "full analysis result",
       "relations", "Open Domain Relations"),
      capCard("▤", "Design Context",
       "Cross-check power intent against a netlist snapshot - instances, ports, PG pins, sequential state.",
       "netlist JSON optional",
       "design", "Open Design"),
      capCard("▦", "Coverage",
       "Is every power domain and supply accounted for? Coverage is not correctness.",
       "full analysis result",
       "coverage", "Open Coverage"),
      capCard("◫", "Readiness",
       "Verdict, blockers, review items and advisories across five dimensions.",
       "full analysis result",
       "readiness", "Open Health"),
    ],
    advanced: [
      capCard("⇄", "UPF Diff",
       "Compare two UPF revisions semantically - domains, supplies, strategies and PST changes, not raw text.",
       "Version A UPF · Version B UPF",
       "diff", "Open Diff"),
      capCard("⌦", "CI Gate",
       "Gate power-intent changes against a policy - PASS/FAIL with reasons and an exit code, as CI sees it.",
       "UPF · policy · optional baseline",
       "gate", "Open CI Gate"),
      capCard("▶", "Test Drive",
       "Run the real workflow on believable samples - clean, buggy, and a V1→V2 regression.",
       "built-in samples",
       "test_drive", "Start Test Drive"),
    ],
    output: [
      capCard("❐", "Reports",
       "HTML / JSON / text reports from real analysis evidence - findings, rule IDs, lines, readiness, support.",
       "UPF or current analysis",
       "reports", "Open Reports"),
      capCard("☰", "Rules",
       `Browse ${_RULE_COUNT()} deterministic rules across six layers - what each detects and why it matters.`,
       "none - reference surface",
       "rules", "Open Rules"),
      capCard("◆", "Trust",
       "What UPF-Insight validates, partially validates, and never claims - the trust boundary, plainly.",
       "none - disclosure surface",
       "trust", "Open Trust"),
      capCard("❐", "Documentation",
       "Repository documentation, CLI reference, and the evidence map - the UPF journey from zero to result.",
       "none - reference surface",
       "documentation", "Open Documentation"),
    ],
  };
  let html = pageHead("UPF-INSIGHT", "What can I do with UPF-Insight?",
    "UPF-Insight runs a deterministic, local analysis of IEEE 1801 power intent - validation, PST intelligence, supply/strategy analysis, design-aware cross-checks, semantic diff, a CI gate, and reports.");
  html += `<div class="hero">
    <div class="hero-actions">
      <button class="btn btn-primary" type="button" data-home-view="test_drive">Start with Test Drive</button>
      <button class="btn btn-primary" type="button" data-home-view="new_analysis">Validate a UPF</button>
      <button class="btn btn-primary" type="button" data-home-view="gate">Run CI Gate</button>
    </div>
  </div>`;
  html += `<div class="wf-strip" role="list" aria-label="primary workflow">
    <div class="wf-step"><span class="wf-k mono">BUILD</span><button class="btn btn-sm" type="button" data-home-view="generator">Generate UPF</button></div>
    <span class="wf-arrow">→</span>
    <div class="wf-step"><span class="wf-k mono">CHECK</span><button class="btn btn-sm" type="button" data-home-view="new_analysis">Validate UPF</button></div>
    <span class="wf-arrow">→</span>
    <div class="wf-step"><span class="wf-k mono">UNDERSTAND</span><button class="btn btn-sm" type="button" data-home-view="overview">Findings</button></div>
    <span class="wf-arrow">→</span>
    <div class="wf-step"><span class="wf-k mono">COMPARE</span><button class="btn btn-sm" type="button" data-home-view="diff">UPF Diff</button></div>
    <span class="wf-arrow">→</span>
    <div class="wf-step"><span class="wf-k mono">GATE</span><button class="btn btn-sm" type="button" data-home-view="gate">CI Gate</button></div>
    <span class="wf-arrow">→</span>
    <div class="wf-step"><span class="wf-k mono">EXPORT</span><button class="btn btn-sm" type="button" data-home-view="reports">Reports / JSON</button></div>
  </div>`;
  html += capGroup("CORE", "the daily power-intent tasks", caps.core);
  html += capGroup("ANALYZE", "understand the intent after a validation run", caps.analyze);
  html += capGroup("ADVANCED", "compare, gate and demonstrate", caps.advanced);
  html += capGroup("OUTPUT & KNOWLEDGE", "evidence, rules and trust", caps.output);
  return html + "</div>";
}

/* ── New Analysis (first-run entry) ─────────────────────────────────────── */
export async function pageNewAnalysis() {
  const has = !!App.state.analysis;
  let html = pageHead("UPF-INSIGHT", "Check your power intent before implementation",
    "Drop in your UPF (IEEE 1801) file - UPF-Insight runs a deterministic check across syntax, references, supply/domain, PST, strategy and design-aware layers.",
    has ? "Analysis loaded - load a new UPF to re-run, or explore the results."
        : "The sample is loaded - press Analyze, or load your own UPF.");
  html += `<div class="input-surface entry">
    <div class="entry-step">
      <div class="es-num">1</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">UPF power-intent file</span><span class="es-req">REQUIRED</span></div>
        <div class="es-actions">
          <button class="btn btn-sm" id="na-pick" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="na-sample" type="button">Load sample</button>
          <button class="btn btn-sm btn-ghost" id="na-clear" type="button">Clear</button>
          <span class="is-file mono" id="na-file">${esc(App.state.filename)}</span>
        </div>
        <textarea class="code-input" id="na-upf" rows="6" spellcheck="false" placeholder="upf_version 3.0&#10;set_design_top top&#10;create_power_domain core -elements {u_core}&#10;...">${esc(App.state.upf)}</textarea>
      </div>
    </div>
    <div class="entry-step">
      <div class="es-num">2</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Design context (netlist JSON)</span><span class="es-opt">OPTIONAL</span></div>
        <p class="es-why">Optional - UPF-only mode validates syntax, references, supply/domain, PST and strategy layers without design context. Adding a design snapshot unlocks the design-aware layer (UPF-080…084).</p>
        <div class="es-actions">
          <button class="btn btn-sm" id="na-net-pick" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="na-net-clear" type="button">Clear</button>
          <span class="is-file mono" id="na-net-file">no design context</span>
        </div>
        <textarea class="opt-text" id="na-netlist" rows="3" spellcheck="false" placeholder='{"instances": {"u_core": {"module": "core", "sequential": true}}, "ports": ["clk"], ...}'></textarea>
      </div>
    </div>
  </div>
  <div class="entry-foot">
    <button class="btn btn-primary btn-lg" id="na-analyze" type="button">Analyze</button>
    <span class="mono" style="font-size:11px;color:var(--text-muted)">runs locally · deterministic · offline · no LLM</span>
  </div>`;
  return html + "</div>";
}

/* ── Findings (Validator) ───────────────────────────────────────────────── */
export async function pageValidator() {
  const a = App.state.analysis;
  const upf = App.state.upf;

  let html = pageHead("RESULTS", "Findings", "What did UPF-Insight find in your power intent? Every finding traces to a rule and a source line.",
                      "Click a finding to inspect its rule and source line.");
  html += `<div class="input-surface">
    <div class="input-surface-head">
      <span class="is-title">Power-intent input</span>
      <span class="is-file" id="val-file">${esc(App.state.filename)}</span>
      <button class="btn btn-sm" id="val-pick" type="button">Choose file…</button>
      <button class="btn btn-sm" id="val-load-sample" type="button">Load sample</button>
      <button class="btn btn-sm btn-ghost" id="val-clear" type="button">Clear</button>
    </div>
    <textarea class="code-input" id="val-upf" spellcheck="false" placeholder="upf_version 3.0&#10;set_design_top top&#10;create_power_domain core -elements {u_core}&#10;...">${esc(upf)}</textarea>
    <div class="optional-panel">
      <div>
        <label class="opt-label" for="val-netlist">Design context (JSON, optional)</label>
        <textarea class="opt-text" id="val-netlist" rows="3" spellcheck="false" placeholder='{"instances": {...}, "ports": [...], ...}'></textarea>
      </div>
    </div>
    <div style="padding:10px 14px;display:flex;gap:10px;align-items:center;border-top:1px solid var(--border-subtle)">
      <button class="btn btn-primary" id="val-analyze" type="button">Analyze</button>
      <span class="mono" style="font-size:11px;color:var(--text-muted)">runs locally · deterministic · offline</span>
    </div>
  </div>`;

  if (!a) {
    html += emptyState("Ready to analyze", "Paste or upload UPF text above, then press Analyze.", "Findings, readiness, coverage and provenance render here after the run.");
    return html + "</div>";
  }

  const c = a.check || {};
  const issues = (c.findings || []).map((it, i) => ({ ...it, _i: i, code: it.rule, msg: it.message, sev: it.severity, obj: findingObj(it), loc: findingLoc(it) }));
  const errs = issues.filter(i => i.sev === "error").length;
  const warns = issues.filter(i => i.sev === "warning").length;
  const infos = issues.filter(i => i.sev === "info").length;

  html += `<div class="mono" style="font-size:12px;color:var(--text-secondary);margin:8px 0">analysis mode: ${esc((a.readiness || {}).mode || "UPF_ONLY")} · ${esc(a.command_count ?? 0)} commands · ${esc(a.file_count ?? 0)} file(s)</div>`;
  html += chips([statusBadge("trust", trustFromSupport(a.support)), statusBadge("readiness", (a.readiness || {}).overall || "-")]);

  html += metricRow([
    { label: "Errors", value: errs }, { label: "Warnings", value: warns },
    { label: "Info", value: infos }, { label: "Commands", value: a.command_count ?? 0 },
  ]);

  if (errs) html += callout(`${errs} error(s) must be reviewed before implementation. A clean check is not a power/IR signoff.`, "error");
  else if (warns) html += callout(`No errors - ${warns} warning(s) need review.`, "warning");
  else html += callout("No errors or warnings within scope. See the support boundary for what was verified - this is not a power/IR signoff.", "info");

  html += `<div class="filters">
    <div class="f-field"><label>Severity</label>${segFilter("sev", ["All", "error", "warning", "info"], App.state.filters.sev)}</div>
    <div class="f-field"><label>Rule</label><select class="select-input" id="f-rule"><option>All</option>${[...new Set(issues.map(i => i.code))].sort().map(c => `<option${c === App.state.filters.rule ? " selected" : ""}>${esc(c)}</option>`).join("")}</select></div>
    <div class="f-field"><label>Search</label><input class="search-input" id="f-q" placeholder="object, message…" value="${esc(App.state.filters.q)}"></div>
    <button class="btn btn-sm btn-ghost" id="f-clear" type="button">Clear filters</button>
  </div>`;

  const f = App.state.filters;
  const ql = f.q.trim().toLowerCase();
  const filtered = issues.filter(it => {
    if (f.sev !== "All" && it.sev !== f.sev) return false;
    if (f.rule !== "All" && it.code !== f.rule) return false;
    if (ql && ![it.msg, it.code, it.obj].some(v => (v || "").toLowerCase().includes(ql))) return false;
    return true;
  });

  if (!issues.length) html += emptyState("No issues found", "No findings within the supported analysis scope.", "Review the support boundary - a clean check is not a power/IR signoff.");
  else if (!filtered.length) html += emptyState("No matching findings", "No findings match the current filters.", "Clear or loosen filters to see the full finding list.");
  else {
    html += `<div class="mono" style="font-size:11px;color:var(--text-muted);margin:6px 0">${filtered.length} of ${issues.length} findings shown</div>`;
    html += table(
      [{ label: "Severity" }, { label: "Rule" }, { label: "Finding" }, { label: "File" }, { label: "Loc" }],
      filtered.map(it => ({ key: `${it.code}-${it.line}-${it._i}`, idx: it._i, cells: [
        { html: statusBadge("severity", it.sev) },
        { html: `<span class="mono">${esc(it.code)}</span>` },
        { html: `<span class="msg">${esc(it.msg)}</span>` },
        { html: `<span class="mono">${esc(it.file || "")}</span>` },
        { html: `<span class="mono">${esc(it.loc)}</span>` },
      ] })),
      { clickable: true }
    );
    html += `<p class="mono" style="font-size:11px;color:var(--text-muted);margin:6px 0 0">Click any row for rule detail, how-to-fix guidance and source context.</p>`;
  }

  html += sectionTitle("Source", "line numbers · finding highlights");
  const hl = {};
  issues.forEach(it => {
    const cls = it.sev === "warning" ? "hl-warn" : "hl";
    if (it.line) hl[it.line] = (hl[it.line] || "") + " " + cls;
  });
  html += sourceViewer(App.state.upf.split("\n"), hl);

  html += renderReadiness(a);
  html += renderCoverage(a);
  html += renderSupport(a);
  return html + "</div>";
}

function renderReadiness(a) {
  const rdy = a.readiness || {};
  if (!rdy.overall) return "";
  let h = sectionTitle("Power-intent readiness", "ready for implementation handoff?");
  h += `<div class="rdy-overall"><div><div class="ro-label">Overall</div><div class="ro-value">${statusBadge("readiness", rdy.overall)}</div></div><div style="margin-left:auto" class="mono" style="font-size:12px;color:var(--text-muted)">mode: ${esc((rdy.mode || "UPF_ONLY").replace(/_/g, " "))}</div></div>`;
  h += readinessRail(rdy);
  (rdy.blockers || []).slice(0, 10).forEach(b => {
    h += `<div class="ilink"><span class="il-rule">${esc(b.code)}</span><span class="il-kind" style="color:var(--error)">${esc(b.tier || "BLOCKER")}</span><span class="il-a">${esc(b.message)}</span>${b.line ? `<span class="il-loc">L${b.line}</span>` : ""}</div>`;
  });
  (rdy.review_items || []).slice(0, 10).forEach(r => {
    h += `<div class="ilink"><span class="il-rule">${esc(r.code)}</span><span class="il-kind" style="color:var(--warning)">${esc(r.tier || "REVIEW")}</span><span class="il-a">${esc(r.message)}</span>${r.line ? `<span class="il-loc">L${r.line}</span>` : ""}</div>`;
  });
  (rdy.advisories || []).slice(0, 10).forEach(ad => {
    h += `<div class="ilink"><span class="il-rule">${esc(ad.code || "ADV")}</span><span class="il-kind" style="color:var(--accent-2)">ADVISORY</span><span class="il-a">${esc(ad.message)}</span></div>`;
  });
  (rdy.notes || []).forEach(n => h += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">- ${esc(n)}</div>`);
  h += `<p class="callout co-warning"><span><strong>READY ≠ signoff</strong> - this is a power-intent review, not a power/IR signoff.</span></p>`;
  return h;
}

function renderCoverage(a) {
  const cov = a.coverage || {};
  if (cov.domain_coverage === undefined && !(cov.domains || []).length) return "";
  let h = sectionTitle("Power-intent coverage", "what the intent touches");
  h += `<p class="callout co-info"><span><strong>Coverage is NOT correctness</strong> - a fully covered design can still have power-intent errors.</span></p>`;
  h += metricRow([
    { label: "Domains covered", value: (cov.domains || []).filter(d => d.covered).length + "/" + (cov.domains || []).length },
    { label: "Unreferenced supplies", value: (cov.unreferenced_supplies || []).length },
    { label: "Declared supplies", value: (cov.declared_supplies || []).length },
  ]);
  if ((cov.domains || []).length) {
    h += table([{ label: "Domain" }, { label: "Primary" }, { label: "Switchable" }, { label: "Isolation" }, { label: "Retention" }, { label: "LS" }, { label: "Status" }],
      cov.domains.map(d => ({ key: d.domain, cells: [
        { html: `<span class="mono">${esc(d.domain)}</span>` },
        d.has_primary_supply ? "yes" : "no",
        d.is_switchable ? "yes" : "no",
        d.has_isolation ? "yes" : "no",
        d.has_retention ? "yes" : "no",
        d.has_level_shifter ? "yes" : "no",
        { html: d.covered ? `<span class="sdc-status sev-success"><span class="sh circ"></span>covered</span>` : `<span class="sdc-status sev-warning"><span class="sh tri"></span>${esc(d.gaps.join(", "))}</span>` },
      ] })));
  }
  return h;
}

function renderSupport(a) {
  const sup = a.support;
  if (!sup) return "";
  let h = sectionTitle("Support boundary", "what was validated · partial · skipped");
  h += `<div class="chips">${statusBadge("trust", trustFromSupport(sup))}</div>`;
  h += metricRow(
    Object.entries(sup.statuses || {}).map(([k, v]) => ({ label: k.replace(/_/g, " "), value: v }))
  );
  (sup.notes || []).forEach(n => h += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">- ${esc(n)}</div>`);
  h += `<p class="callout co-info"><span><strong>Deterministic engine</strong> - no LLM, no model inference. Analysis is local, reproducible and offline-capable.</span></p>`;
  return h;
}

/* ── Supply Network ─────────────────────────────────────────────────────── */
export async function pageSupply() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Supply Network", "Domains, supply ports/nets/sets and power switches behind your power intent.",
                      "Provide a UPF below and press Analyze - the supply network renders here.");
  if (!a || !a.model) {
    html += standaloneAnalyzeHtml("Supply Network", "Drop your IEEE 1801 UPF in here - domains, supply ports/nets/sets and switches render in place.");
    return html + "</div>";
  }
  const m = a.model || {};
  html += metricRow([
    { label: "Domains", value: Object.keys(m.domains || {}).length },
    { label: "Supply ports", value: Object.keys(m.supply_ports || {}).length },
    { label: "Supply nets", value: Object.keys(m.supply_nets || {}).length },
    { label: "Supply sets", value: Object.keys(m.supply_sets || {}).length },
    { label: "Switches", value: Object.keys(m.switches || {}).length },
  ]);

  const domains = Object.values(m.domains || {});
  if (domains.length) {
    html += sectionTitle("Power domains", `${domains.length} domain(s)`);
    html += table([{ label: "Domain" }, { label: "Scope" }, { label: "Elements" }, { label: "Primary supply" }],
      domains.map(d => ({ key: d.name, cells: [
        { html: `<span class="mono">${esc(d.name)}</span>` }, esc(d.scope || "."),
        { html: `<span class="msg mono">${esc((d.elements || []).join(", "))}</span>` },
        { html: `<span class="mono">${esc(Object.values(d.primary_supply_sets || {}).join(", "))}</span>` },
      ] })));
  }

  const sws = Object.values(m.switches || {});
  if (sws.length) {
    html += sectionTitle("Power switches");
    html += table([{ label: "Switch" }, { label: "Input" }, { label: "Output" }, { label: "Control" }, { label: "On state" }],
      sws.map(s => ({ key: s.name, cells: [
        { html: `<span class="mono">${esc(s.name)}</span>` }, esc(s.input_supply || "-"), esc(s.output_supply || "-"),
        esc(s.control_port || "-"), esc(s.on_state || "-"),
      ] })));
  }

  const sets = Object.values(m.supply_sets || {});
  if (sets.length) {
    html += sectionTitle("Supply sets");
    html += table([{ label: "Set" }, { label: "Functions" }],
      sets.map(s => ({ key: s.name, cells: [
        { html: `<span class="mono">${esc(s.name)}</span>` },
        { html: `<span class="msg mono">${esc(Object.entries(s.functions || {}).map(([k, v]) => `${k}: ${v}`).join(" · "))}</span>` },
      ] })));
  }
  return html + "</div>";
}

/* ── Power State Table ──────────────────────────────────────────────────── */
export async function pagePST() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Power States", "Declared supply states and the Power State Table (PST) rows.",
                      "Provide a UPF below and press Analyze - the PST matrix renders here.");
  if (!a) {
    html += standaloneAnalyzeHtml("Power States", "Drop your IEEE 1801 UPF in here - declared supply states and the PST matrix render in place.");
    return html + "</div>";
  }
  const pst = a.pst || {};
  const m = a.model || {};
  const states = (m.supply_states || []);
  html += metricRow([
    { label: "PST", value: pst.pst_name || "-" }, { label: "PST states", value: pst.state_count ?? 0 },
    { label: "Declared states", value: (pst.declared_supply_states || []).length },
    { label: "Used", value: (pst.used_supply_states || []).length },
    { label: "Unused", value: (pst.unused_states || []).length },
    { label: "Undeclared", value: (pst.undeclared_states || []).length },
  ]);
  if (pst.coverage_note) html += `<p class="callout ${pst.undeclared_states && pst.undeclared_states.length ? "co-warning" : "co-info"}"><span><strong>Coverage</strong> - ${esc(pst.coverage_note)}</span></p>`;

  if (states.length) {
    html += sectionTitle("Declared supply states", `${states.length} state(s)`);
    html += table([{ label: "State" }, { label: "Parent" }, { label: "Type" }, { label: "Voltage" }],
      states.map(s => ({ key: s.name + (s.parent || ""), cells: [
        { html: `<span class="mono">${esc(s.name)}</span>` }, esc(s.parent || "-"), esc(s.type || "supply_state"),
        { html: `<span class="num">${s.voltage != null ? esc(s.voltage) + " V" : "-"}</span>` },
      ] })));
  }

  if (Object.keys(m.psts || {}).length) {
    html += sectionTitle("PST rows");
    Object.values(m.psts || {}).forEach(p => {
      html += pstMatrixHtml(p);
    });
    html += sectionTitle("Transitions");
    html += `<div class="mono" style="font-size:12px;color:var(--text-secondary)">${esc((pst.transitions || []).map(t => `${t[0]} → ${t[1]}`).join(" · ") || "-")}</div>`;
  }
  return html + "</div>";
}

/* ── Strategies ─────────────────────────────────────────────────────────── */
export async function pageStrategies() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Strategies", "Isolation, retention and level-shifter strategies in your power intent.",
                      "Provide a UPF below and press Analyze - the strategy tables render here.");
  if (!a || !a.model) {
    html += standaloneAnalyzeHtml("Strategies", "Drop your IEEE 1801 UPF in here - isolation, retention and level-shifter strategies render in place.");
    return html + "</div>";
  }
  const m = a.model || {};
  html += metricRow([
    { label: "Isolation", value: (m.isolation || []).length },
    { label: "Level shifters", value: (m.level_shifters || []).length },
    { label: "Retention", value: (m.retentions || []).length },
  ]);
  if ((m.isolation || []).length) {
    html += sectionTitle("Isolation", `${(m.isolation || []).length} strategy(ies)`);
    html += table([{ label: "Domain" }, { label: "Location" }, { label: "Clamp" }, { label: "Applies to" }, { label: "Control" }, { label: "Supply" }],
      m.isolation.map(s => ({ key: s.domain + (s.control_signal || ""), cells: [
        { html: `<span class="mono">${esc(s.domain)}</span>` }, esc(s.location || "self"), esc(s.clamp_value || "-"),
        esc(s.applies_to || "outputs"), esc(s.control_signal || "-"), esc(s.isolation_supply || "-"),
      ] })));
  }
  if ((m.level_shifters || []).length) {
    html += sectionTitle("Level shifters", `${(m.level_shifters || []).length} strategy(ies)`);
    html += table([{ label: "Domain" }, { label: "Location" }, { label: "Rule" }, { label: "Threshold" }],
      m.level_shifters.map(s => ({ key: s.domain, cells: [
        { html: `<span class="mono">${esc(s.domain)}</span>` }, esc(s.location || "self"), esc(s.rule || "low_to_high"),
        { html: `<span class="num">${s.threshold != null ? esc(s.threshold) : "-"}</span>` },
      ] })));
  }
  if ((m.retentions || []).length) {
    html += sectionTitle("Retention", `${(m.retentions || []).length} strategy(ies)`);
    html += table([{ label: "Domain" }, { label: "Supply" }, { label: "Save" }, { label: "Restore" }],
      m.retentions.map(s => ({ key: s.domain, cells: [
        { html: `<span class="mono">${esc(s.domain)}</span>` }, esc(s.retention_supply || "-"), esc(s.save_signal || "-"), esc(s.restore_signal || "-"),
      ] })));
  }
  return html + "</div>";
}

/* ── Design context ─────────────────────────────────────────────────────── */
export async function pageDesign() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Design", "The netlist snapshot behind your design-aware rules (UPF-080…084).",
                      "Provide a UPF below and press Analyze - the design-aware layer renders here when a netlist snapshot is supplied.");
  if (!a) {
    html += standaloneAnalyzeHtml("Design", "Drop your IEEE 1801 UPF in here. The design-aware layer (UPF-080…084) also needs a netlist snapshot - without one, UPF-only analysis still runs and reports the boundary honestly.");
    return html + "</div>";
  }
  const design = (a.model || {}).design;
  if (!design) {
    html += emptyState("Design context not supplied", "The design-aware layer (UPF-080…084) is silent without a design snapshot.", "Add the design JSON in New Analysis and re-analyze.");
    return html + "</div>";
  }
  html += `<p class="callout co-info"><span><strong>Design-aware rules active</strong> - UPF-080…084 validate instances, control signals, crossings, retention coverage and PG pins against this snapshot.</span></p>`;
  const inst = design.instances || {};
  const instKeys = Object.keys(inst);
  html += metricRow([
    { label: "Instances", value: instKeys.length },
    { label: "Ports", value: (design.ports || []).length },
    { label: "Signals", value: Object.keys(design.signals || {}).length },
    { label: "Modules (PG pins)", value: Object.keys(design.pg_pins || {}).length },
  ]);
  if (instKeys.length) {
    html += sectionTitle("Instances", `${instKeys.length} instance(s)`);
    html += table([{ label: "Instance" }, { label: "Module" }, { label: "Sequential" }],
      instKeys.map(n => ({ key: n, cells: [
        { html: `<span class="mono">${esc(n)}</span>` },
        { html: `<span class="mono">${esc(inst[n].module || "-")}</span>` },
        inst[n].sequential ? "yes" : "no",
      ] })));
  }
  if ((design.ports || []).length) {
    html += sectionTitle("Ports");
    html += `<div class="mono" style="font-size:12px;color:var(--text-secondary)">${esc(design.ports.join(", "))}</div>`;
  }
  if (Object.keys(design.pg_pins || {}).length) {
    html += sectionTitle("PG pins", "module → liberty-style power/ground pins");
    html += table([{ label: "Module" }, { label: "PG pins" }],
      Object.entries(design.pg_pins || {}).map(([m, pins]) => ({ key: m, cells: [
        { html: `<span class="mono">${esc(m)}</span>` },
        { html: `<span class="msg mono">${esc(pins.join(", "))}</span>` },
      ] })));
  }
  const designFindings = ((a.check || {}).findings || []).filter(f => f.rule && f.rule.startsWith("UPF-08"));
  if (designFindings.length) {
    html += sectionTitle(`Design-aware findings (${designFindings.length})`);
    designFindings.forEach(f => {
      html += `<div class="ilink"><span class="il-rule">${esc(f.rule)}</span><span class="il-kind" style="color:${f.severity === "error" ? "var(--error)" : "var(--warning)"}">${esc(f.severity)}</span><span class="il-a">${esc(f.message)}</span>${f.line ? `<span class="il-loc">L${f.line}</span>` : ""}</div>`;
    });
  }
  return html + "</div>";
}

/* ── Coverage ───────────────────────────────────────────────────────────── */
export async function pageCoverage() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Coverage", "Is every power domain and supply accounted for?",
                      "A fully covered design is not a correct design - provide a UPF below and press Analyze.");
  if (!a || !a.coverage || a.coverage.domain_coverage === undefined) {
    html += standaloneAnalyzeHtml("Coverage", "Drop your IEEE 1801 UPF in here - domain and supply coverage renders in place. Coverage is not correctness.");
    return html + "</div>";
  }
  const cov = a.coverage;
  html += `<p class="callout co-info"><span><strong>Coverage is NOT correctness</strong> - coverage reports what the intent touches, never that it is right.</span></p>`;
  html += metricRow([
    { label: "Domain coverage", value: Math.round(cov.domain_coverage * 100) + "%" },
    { label: "Supply coverage", value: Math.round(cov.supply_coverage * 100) + "%" },
    { label: "Declared supplies", value: (cov.declared_supplies || []).length },
    { label: "Referenced", value: (cov.referenced_supplies || []).length },
    { label: "Unreferenced", value: (cov.unreferenced_supplies || []).length },
  ]);
  if ((cov.domains || []).length) {
    html += sectionTitle("Domain detail", `${cov.domains.length} domains`);
    html += table([{ label: "Domain" }, { label: "Primary" }, { label: "Switchable" }, { label: "Isolation" }, { label: "Retention" }, { label: "LS" }, { label: "Status" }],
      cov.domains.map(d => ({ key: d.domain, cells: [
        { html: `<span class="mono">${esc(d.domain)}</span>` },
        d.has_primary_supply ? "yes" : "no", d.is_switchable ? "yes" : "no",
        d.has_isolation ? "yes" : "no", d.has_retention ? "yes" : "no", d.has_level_shifter ? "yes" : "no",
        { html: d.covered ? `<span class="sdc-status sev-success"><span class="sh circ"></span>covered</span>` : `<span class="sdc-status sev-warning"><span class="sh tri"></span>${esc(d.gaps.join(", "))}</span>` },
      ] })));
  }
  if ((cov.unreferenced_supplies || []).length) {
    html += sectionTitle("Unreferenced supplies");
    html += `<div class="mono" style="font-size:12px;color:var(--text-secondary)">${esc(cov.unreferenced_supplies.join(", "))}</div>`;
  } else {
    html += `<p class="callout co-success"><span><strong>All declared supplies are referenced</strong> - no unreferenced supplies.</span></p>`;
  }
  return html + "</div>";
}

/* ── Domain Relations (Power Domain Relation Matrix) ────────────────────── */
export async function pageRelations() {
  const a = App.state.analysis;
  let html = pageHead("ANALYZE", "Domain Relations", "The power-domain relation graph: which domains interact, how they are powered, and where each domain is owned - three views of one canonical model, every cell derived with provenance, never inferred in the UI.",
                      "Analyze a UPF below to see the relation matrix, supply network and hierarchy map, then click any matrix cell for its evidence.");
  if (!a || !a.relations) {
    html += standaloneAnalyzeHtml("Domain Relations", "Drop your IEEE 1801 UPF in here - the power-domain relation matrix, supply network, domain types and topology render in place. A supply shared between domains is NOT shown as an interaction; empty cells mean no proven crossing.");
    return html + "</div>";
  }
  const rel = a.relations;
  const domains = rel.domains || [];
  const relations = rel.relations || [];
  const matrix = rel.matrix || {};
  const names = domains.map(d => d.name);
  const nAon = domains.filter(d => d.type === "ALWAYS_ON").length;
  const nSw = domains.filter(d => d.type === "SWITCHABLE").length;
  const nUnk = domains.filter(d => d.type === "UNKNOWN").length;

  html += metricRow([
    { label: "Architecture", value: rel.architecture || "-" },
    { label: "Domains", value: domains.length },
    { label: "Always-on", value: nAon },
    { label: "Switchable", value: nSw },
    { label: "Unknown type", value: nUnk },
    { label: "Relations", value: relations.length },
  ]);

  // ---- Domain cards with EXPLICIT relationships (never a bare "related") ----
  html += sectionTitle("Power domains", "power type is evidence-based: SWITCHABLE requires switch evidence, ALWAYS-ON requires explicit always-on evidence, otherwise UNKNOWN");
  html += `<div class="rel-dom-grid">`;
  domains.forEach(d => {
    const tBadge = d.type === "SWITCHABLE"
      ? `<span class="sdc-status sev-warning"><span class="sh tri"></span>SWITCHABLE</span>`
      : d.type === "ALWAYS_ON"
        ? `<span class="sdc-status sev-success"><span class="sh circ"></span>ALWAYS-ON</span>`
        : `<span class="sdc-status sev-muted"><span class="sh circ"></span>UNKNOWN</span>`;
    const outRels = relations.filter(r => r.from_domain === d.name);
    const inRels = relations.filter(r => r.to_domain === d.name);
    const outList = outRels.map(r => `${esc(r.to_domain)} · ${esc(r.label)}`).join(", ") || "none";
    const inList = inRels.map(r => `${esc(r.from_domain)} · ${esc(r.label)}`).join(", ") || "none";
    html += `<div class="rel-dom-card" data-rel-type="${escAttr(d.type)}">
      <div class="rel-dom-head"><span class="mono rel-dom-name">${esc(d.name)}</span>${tBadge}</div>
      <div class="kv" style="margin-top:8px">
        <dt>Scope</dt><dd class="mono">${esc(d.scope || ".")}</dd>
        <dt>Power</dt><dd class="mono">${esc(d.primary_power || "-")}</dd>
        <dt>Ground</dt><dd class="mono">${esc(d.primary_ground || "-")}</dd>
        <dt>Switch</dt><dd class="mono">${esc(d.switch || "-")}</dd>
        <dt>Elements</dt><dd class="mono">${esc((d.elements || []).join(", ") || "-")}</dd>
        <dt>Outbound</dt><dd class="mono">${esc(outList)}</dd>
        <dt>Inbound</dt><dd class="mono">${esc(inList)}</dd>
        ${d.declared_file ? `<dt>Source</dt><dd class="mono">${esc(d.declared_file)}${d.declared_line ? ":L" + esc(String(d.declared_line)) : ""}</dd>` : ""}
      </div>
    </div>`;
  });
  html += `</div>`;

  // ---- Matrix: cross-domain interactions ONLY (supply sharing is separate) ----
  html += sectionTitle("Power Domain Relation Matrix", "FROM row -> TO column · ISO isolation · LS level shift · ISO+LS both · RET retention · SW switch · CTRL control - sharing a supply is NOT an interaction and never appears here");
  if (!names.length) {
    html += emptyState("No domains", "The model has no power domains to relate.", "Add create_power_domain commands and re-analyze.");
  } else {
    html += `<div class="matrix-wrap"><table class="matrix">`;
    html += `<thead><tr><th class="corner">FROM \ TO</th>${names.map(n => `<th>${esc(n)}</th>`).join("")}</tr></thead><tbody>`;
    names.forEach(f => {
      html += `<tr><td class="corner mono">${esc(f)}</td>`;
      names.forEach(t => {
        const label = f === t ? "-" : (matrix[f] || {})[t] || "";
        const cls = f === t ? "cell mx-unknown" : !label ? "cell mx-unknown" : label.indexOf("ISO") >= 0 ? "cell mx-excl" : "cell mx-sync";
        html += `<td class="${cls}" data-rel-cell="${escAttr(f)}|${escAttr(t)}" title="${f === t ? esc(f) + " (self)" : label ? esc(f) + " -> " + esc(t) + ": " + esc(label) : esc(f) + " -> " + esc(t) + ": no proven interaction"}">${f === t ? "·" : label ? esc(label) : ""}</td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table></div>`;
    html += `<p class="mono" style="font-size:11px;color:var(--text-muted)">Empty cells are honest: no proven cross-domain interaction. Click a filled cell for evidence, provenance and next actions.</p>`;
  }

  // ---- Relation list with evidence ----
  if (relations.length) {
    html += sectionTitle("Relations", `${relations.length} proven interaction(s) with provenance`);
    relations.forEach(r => {
      const ev = (r.evidence || [])[0];
      const loc = ev && ev.line ? ` L${ev.line}${ev.file ? " in " + esc(ev.file) : ""}` : "";
      html += `<div class="ilink" data-rel-detail="${escAttr(r.from_domain)}|${escAttr(r.to_domain)}">
        <span class="il-rule">${esc(r.from_domain)} → ${esc(r.to_domain)}</span>
        <span class="il-kind" style="color:var(--accent)">${esc(r.label)}</span>
        <span class="il-a">${ev ? esc(ev.detail) + "<span class=\"mono\" style=\"color:var(--text-muted)\">" + esc(loc) + "</span>" : "no evidence recorded"}</span>
        <span class="il-loc"><button class="btn btn-sm btn-ghost" data-rel-ev="${escAttr(r.from_domain)}|${escAttr(r.to_domain)}" type="button">Evidence</button></span>
      </div>`;
    });
  } else {
    html += `<p class="callout co-info"><span><strong>No interactions detected</strong> - the engine found no switch, isolation, level-shift, retention or control link between domains. Empty matrix cells are not defects; they mean no proven crossing.</span></p>`;
  }

  // ---- Supply network: separate from domain relations ----
  const sharing = rel.supply_sharing || {};
  html += sectionTitle("Supply network", "which supply powers which domains - a shared net is not a domain interaction");
  if (Object.keys(sharing).length) {
    html += table([{ label: "Supply" }, { label: "Domains" }],
      Object.entries(sharing).map(([net, ds]) => ({ key: net, cells: [
        { html: `<span class="mono">${esc(net)}</span>` },
        { html: `<span class="mono">${esc(ds.join(", "))}</span>` },
      ] })));
  } else {
    html += `<p class="callout co-info"><span><strong>No supply mapping</strong> - no domain has a resolvable primary power/ground net.</span></p>`;
  }

  // ---- Hierarchy map: file / scope / owner ownership ----
  const hier = rel.hierarchy || [];
  html += sectionTitle("Domain ownership", rel.architecture === "HIERARCHICAL" ? "UPF file · scope · owning RTL instance - where each domain is defined" : "flat design - every domain lives in the top scope");
  if (hier.length) {
    html += table([{ label: "Domain" }, { label: "UPF file" }, { label: "Scope" }, { label: "Owner" }],
      hier.map(h => ({ key: h.domain + (h.scope || ""), cells: [
        { html: `<span class="mono">${esc(h.domain)}</span>` },
        { html: `<span class="mono">${esc(h.upf_file || "-")}</span>` },
        { html: `<span class="mono">${esc(h.scope || ".")}</span>` },
        { html: `<span class="mono">${esc(h.owner || "-")}</span>` },
      ] })));
  }
  if (rel.architecture === "HIERARCHICAL" && (rel.files || []).length) {
    html += `<div class="mono" style="font-size:11.5px;color:var(--text-secondary);margin-top:8px">UPF project: ${esc(rel.files.join(" · "))}</div>`;
  }

  // ---- Supply maps: load_upf -supply (local supply -> parent supply) ----
  const smaps = rel.supply_maps || [];
  if (rel.architecture === "HIERARCHICAL" && smaps.length) {
    html += sectionTitle("Supply maps", "load_upf -supply binds each child's local supply to a parent supply - the integration contract across hierarchy");
    html += table([{ label: "Scope" }, { label: "Local supply" }, { label: "Parent supply" }, { label: "Source" }],
      smaps.map(m => ({ key: (m.scope || "") + m.local + m.line, cells: [
        { html: `<span class="mono">${esc(m.scope || ".")}</span>` },
        { html: `<span class="mono">${esc(m.local || "-")}</span>` },
        { html: `<span class="mono">${esc(m.parent || "-")}</span>` },
        { html: `<span class="mono">${esc(m.file ? String(m.file).split(/[\\/]/).pop() : "-")}${m.line ? ":L" + String(m.line) : ""}</span>` },
      ] })));
  }

  // ---- Topology: AON anchors, switchable leaves, unclassified - never nested ----
  const aon = domains.filter(d => d.type === "ALWAYS_ON").map(d => d.name);
  const sw = domains.filter(d => d.type === "SWITCHABLE").map(d => d.name);
  const others = domains.filter(d => d.type === "UNKNOWN").map(d => d.name);
  html += sectionTitle("Power topology", "always-on anchors and switchable leaves; unclassified domains are listed separately, never drawn as if they belong to the AON area");
  html += `<div class="rel-topo">`;
  html += `<div class="rel-topo-block"><div class="rel-topo-label">ALWAYS-ON ANCHORS</div><div class="rel-topo-body">${aon.length ? aon.map(n => `<span class="rel-topo-node rel-topo-aon">${esc(n)}</span>`).join("") : `<span class="rel-topo-none">No always-on domain identified - the model has no switch or explicit always-on evidence.</span>`}</div></div>`;
  if (sw.length) {
    html += `<div class="rel-topo-edge">│</div>`;
    html += `<div class="rel-topo-block"><div class="rel-topo-label">SWITCHABLE</div><div class="rel-topo-body">${sw.map(n => `<span class="rel-topo-node rel-topo-sw">${esc(n)}</span>`).join("")}</div></div>`;
  }
  if (others.length) {
    html += `<div class="rel-topo-edge">│</div>`;
    html += `<div class="rel-topo-block"><div class="rel-topo-label">UNCLASSIFIED</div><div class="rel-topo-body">${others.map(n => `<span class="rel-topo-node rel-topo-unk">${esc(n)}</span>`).join("")}</div></div>`;
  }
  html += `</div>`;
  html += `<p class="callout co-info"><span><strong>Matrix semantics</strong> - cells show cross-domain interactions the engine can prove from the model. Empty cells are honest, supply sharing is a separate view, and a relation is never invented by the UI.</span></p>`;
  return html + "</div>";
}

/* ── Readiness (Health) ─────────────────────────────────────────────────── */
export async function pageReadiness() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Health", "Is this power intent ready to hand to implementation?",
                      "Resolve blockers first, then review items - provide a UPF below and press Analyze.");
  if (!a || !a.readiness || !a.readiness.overall) {
    html += standaloneAnalyzeHtml("Health", "Drop your IEEE 1801 UPF in here - the five-dimension readiness verdict renders in place. READY is not a signoff.");
    return html + "</div>";
  }
  const rdy = a.readiness;
  html += `<div class="rdy-overall"><div><div class="ro-label">Overall readiness</div><div class="ro-value">${statusBadge("readiness", rdy.overall)}</div></div><div style="margin-left:auto" class="mono" style="font-size:12px;color:var(--text-muted)">mode: ${esc((rdy.mode || "UPF_ONLY").replace(/_/g, " "))}</div></div>`;
  html += readinessRail(rdy);
  if (rdy.blockers && rdy.blockers.length) {
    html += sectionTitle(`Blockers (${rdy.blockers.length})`);
    rdy.blockers.forEach(b => html += `<div class="ilink"><span class="il-rule">${esc(b.code)}</span><span class="il-kind" style="color:var(--error)">${esc(b.tier || "BLOCKED")}</span><span class="il-a">${esc(b.message)}</span>${b.line ? `<span class="il-loc">L${b.line}</span>` : ""}</div>`);
  }
  if (rdy.review_items && rdy.review_items.length) {
    html += sectionTitle(`Review items (${rdy.review_items.length})`);
    rdy.review_items.forEach(r => html += `<div class="ilink"><span class="il-rule">${esc(r.code)}</span><span class="il-kind" style="color:var(--warning)">${esc(r.tier || "REVIEW")}</span><span class="il-a">${esc(r.message)}</span>${r.line ? `<span class="il-loc">L${r.line}</span>` : ""}</div>`);
  }
  if (rdy.advisories && rdy.advisories.length) {
    html += sectionTitle(`Advisories (${rdy.advisories.length})`);
    rdy.advisories.forEach(ad => html += `<div class="ilink"><span class="il-rule">${esc(ad.code || "ADV")}</span><span class="il-kind" style="color:var(--accent-2)">ADVISORY</span><span class="il-a">${esc(ad.message)}</span></div>`);
  }
  (rdy.notes || []).forEach(n => html += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">- ${esc(n)}</div>`);
  html += `<p class="callout co-warning"><span><strong>READY ≠ signoff</strong> - READY means no rule fired within the supported scope. It is not a power/IR signoff.</span></p>`;
  return html + "</div>";
}

/* ── Support / Trust boundary ───────────────────────────────────────────── */
export async function pageSupport() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Support", "What UPF-Insight validated, partially validated, and skipped.",
                      "A clean result means 'no rule fired', never 'power intent proven correct' - provide a UPF below and press Analyze.");
  if (!a || !a.support) {
    html += standaloneAnalyzeHtml("Support", "Drop your IEEE 1801 UPF in here - the validated/partial/skipped boundary renders in place.");
    return html + "</div>";
  }
  const sup = a.support;
  html += `<div class="chips">${statusBadge("trust", trustFromSupport(sup))}</div>`;
  html += sectionTitle("Boundary counts");
  html += metricRow(
    Object.entries(sup.statuses || {}).map(([k, v]) => ({ label: k.replace(/_/g, " "), value: v }))
  );
  (sup.notes || []).forEach(n => html += `<div class="ilink"><span class="il-rule">NOTE</span><span class="il-a">${esc(n)}</span></div>`);
  html += `<p class="callout co-info"><span><strong>Deterministic engine</strong> - no LLM, no model inference, no external AI APIs. Local, reproducible, offline-capable.</span></p>`;
  return html + "</div>";
}

/* ── Rules ──────────────────────────────────────────────────────────────── */
/* SDC Rules Reference style: search + filters + stat cards + downloads,
   then collapsible rule cards per layer. Only real registry fields are shown
   (code, severity, layer, title, description) - nothing fabricated. */
export async function pageRules() {
  if (!App.state.rules) {
    try { App.state.rules = (await get("/api/rules")).rules || []; }
    catch (e) { App.state.rules = []; }
  }
  const all = App.state.rules || [];
  const q = (App.state.ruleQ || "").toLowerCase();
  const sev = App.state.ruleFilter || "All";
  const layer = App.state.ruleLayer || "All";
  const layers = ["All", ...new Set(all.map(r => r.layer))];
  let rules = all.filter(r =>
    (sev === "All" || r.severity === sev) &&
    (layer === "All" || r.layer === layer) &&
    (!q || (r.code + " " + r.title + " " + r.description).toLowerCase().includes(q)));
  const nErr = rules.filter(r => r.severity === "error").length;
  const nWarn = rules.filter(r => r.severity === "warning").length;
  const nInfo = rules.filter(r => r.severity === "info").length;

  let html = pageHead("TOOLS", "Rules Reference", `All ${all.length} rule codes across six layers.`);
  html += `<div class="rules-toolbar">
    <button class="btn btn-primary" id="rules-gen" type="button">Generate UPF</button>
    <div class="filters">
      <div class="f-field f-grow"><label>Search</label><input class="opt-input" id="rule-q" type="text" placeholder="UPF-060, retention, isolation..." value="${escAttr(App.state.ruleQ || "")}" aria-label="Search rules"></div>
      <div class="f-field"><label>Layer</label><select class="opt-select" id="rule-layer">${layers.map(l => `<option value="${escAttr(l)}"${l === layer ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>
      <div class="f-field"><label>Severity</label>${segFilter("rule-sev", ["All", "error", "warning", "info"], sev)}</div>
    </div>
  </div>`;
  html += `<div class="stat-grid">
    <div class="stat-card sc-blue"><span class="sc-icon">🔍</span><span class="sc-num">${rules.length}</span><span class="sc-label">FILTERED</span></div>
    <div class="stat-card sc-red"><span class="sc-icon">●</span><span class="sc-num">${nErr}</span><span class="sc-label">ERRORS</span></div>
    <div class="stat-card sc-orange"><span class="sc-icon">●</span><span class="sc-num">${nWarn}</span><span class="sc-label">WARNINGS</span></div>
    <div class="stat-card sc-gray"><span class="sc-icon">ℹ</span><span class="sc-num">${nInfo}</span><span class="sc-label">INFO</span></div>
  </div>`;
  html += `<div class="rules-dl">
    <button class="btn btn-sm" id="rules-dl-json" type="button">⬇ Download JSON</button>
    <button class="btn btn-sm" id="rules-dl-md" type="button">⬇ Download Markdown</button>
    <span class="mono" style="font-size:11px;color:var(--text-muted)">real registry data - ${rules.length} rule(s)</span>
  </div>`;

  if (!rules.length) {
    html += emptyState("No rules match", "No rules match the current search and filters.", "Clear or loosen the filters to see the full registry.");
    return html + "</div>";
  }
  const byLayer = {};
  rules.forEach(r => (byLayer[r.layer] = byLayer[r.layer] || []).push(r));
  Object.entries(byLayer).forEach(([layerName, rs]) => {
    html += `<details class="rule-module"${layer === "All" ? " open" : ""}>
      <summary><span class="rm-chev">▼</span><span class="rm-name">${esc(layerName.toLowerCase())} (${rs.length} rule${rs.length === 1 ? "" : "s"})</span></summary>
      <div class="rm-body">`;
    rs.forEach(r => {
      const sevColor = r.severity === "error" ? "var(--error)" : r.severity === "warning" ? "var(--warning)" : "var(--text-muted)";
      html += `<details class="rule-card" data-code="${escAttr(r.code)}">
        <summary class="rc-summary"><span class="rc-sev" style="color:${sevColor}">●</span><span class="rc-code">${esc(r.code)}</span><span class="rc-title">${esc(r.title)}</span></summary>
        <div class="rc-body">
          <div class="rc-meta">${statusBadge("severity", r.severity)}<span class="rc-chip">${esc(r.layer)}</span></div>
          <p class="rc-desc">${esc(r.description)}</p>
          ${RULE_FIXES[r.code] ? `<div class="rc-fix"><div class="rc-fix-k">How to fix</div><p class="rc-fix-t">${esc(RULE_FIXES[r.code])}</p></div>` : ""}
        </div>
      </details>`;
    });
    html += `</div></details>`;
  });
  return html + "</div>";
}

/* ── Export ─────────────────────────────────────────────────────────────── */
export async function pageExport() {
  let html = pageHead("RESULTS", "Export", "Real exportable evidence - JSON result, readiness snapshot (CLI).");
  const a = App.state.analysis;
  if (!a) {
    html += emptyState("Nothing to export", "Run a validation first, then export the evidence.", "Open New Analysis and press Analyze.");
    return html + "</div>";
  }
  html += `<div class="ilink"><span class="il-rule">JSON</span><span class="il-kind" style="color:var(--accent-2)">RESULT</span><span class="il-a">Complete machine-readable validation result (findings, support, readiness, coverage, model).</span><span class="il-loc"><button class="btn btn-sm" id="exp-json" type="button">Download</button></span></div>`;
  html += `<div class="ilink"><span class="il-rule">READINESS</span><span class="il-kind" style="color:var(--accent-2)">EVIDENCE</span><span class="il-a">Serialized readiness object for the current run (JSON).</span><span class="il-loc"><button class="btn btn-sm" id="exp-rdy" type="button">Download</button></span></div>`;
  html += sectionTitle("CLI equivalents", "canonical snapshot flow");
  html += `<div class="kv" style="margin:8px 0">`;
  html += `<dt>Validate</dt><dd><span class="mono">upf-insight check design.upf</span></dd>`;
  html += `<dt>JSON</dt><dd><span class="mono">upf-insight check design.upf --json result.json</span></dd>`;
  html += `<dt>With design</dt><dd><span class="mono">upf-insight check design.upf --netlist design.json</span></dd>`;
  html += `</div>`;
  return html + "</div>";
}

/* ── Trust model ────────────────────────────────────────────────────────── */
export async function pageTrust() {
  let html = pageHead("TOOLS", "Trust Model", "What UPF-Insight validates, what it partially validates, and what it does not claim.");
  html += sectionTitle("Boundary statements");
  [
    ["READY ≠ SIGNOFF", "READY means the power intent satisfies the validator's supported, evidence-backed criteria - not that power/IR or timing passes."],
    ["COVERAGE ≠ CORRECTNESS", "A fully covered design does not prove correct power intent."],
    ["STRUCTURAL ≠ IMPLEMENTED", "Resolving references and strategies does not prove the implemented power network matches the intent."],
  ].forEach(([t, d]) => html += `<div class="ilink"><span class="il-rule">≠</span><span class="il-kind" style="color:var(--warning)">${esc(t)}</span><span class="il-a">${esc(d)}</span></div>`);
  html += sectionTitle("What UPF-Insight validates");
  [
    "UPF syntax and semantic validity for supported constructs",
    "Reference integrity: undefined, duplicate, use-before-definition",
    "Supply & domain integrity: primary supplies, overlaps, connectivity",
    "Power state table consistency and strategy conditioning",
    "Isolation / retention / level-shifter strategy lint",
    "Design-aware checks against a supplied netlist snapshot (UPF-080…084)",
    "Readiness across five dimensions with deterministic actions",
  ].forEach(t => html += `<div class="ilink"><span class="il-rule">✓</span><span class="il-a">${esc(t)}</span></div>`);
  html += sectionTitle("What requires design context or implementation signoff");
  [
    "Design-aware checks (UPF-080…084) → requires a netlist snapshot",
    "Power/IR drop, electromigration, thermal, timing closure → requires implementation signoff tools",
  ].forEach(t => html += `<div class="ilink"><span class="il-rule">△</span><span class="il-a">${esc(t)}</span></div>`);
  html += `<p class="callout co-info"><span><strong>Deterministic engine</strong> - no LLM, no model inference, no external AI APIs. Analysis is local, reproducible and offline-capable.</span></p>`;
  return html + "</div>";
}

/* ── Documentation ──────────────────────────────────────────────────────── */
export async function pageDocumentation() {
  let html = pageHead("TOOLS", "Documentation", "Repository documentation, CLI reference and evidence - real entries only.");
  const rules = App.state.rules;
  html += `<div class="kv" style="margin:8px 0">`;
  html += `<dt>Engine</dt><dd class="mono">deterministic · local-first · offline-capable</dd>`;
  html += `<dt>Rules</dt><dd class="mono">${rules ? rules.length + " deterministic rules across six layers" : "loaded on demand"}</dd>`;
  html += `<dt>CLI</dt><dd class="mono">upf-insight check · model · pst · report · web</dd>`;
  html += `</div>`;
  html += sectionTitle("Reference");
  html += `<div class="ilink"><span class="il-rule">ROOT</span><span class="il-a">README.md - product overview and quick start</span></div>`;
  html += `<div class="ilink"><span class="il-rule">RULES</span><span class="il-a">docs/upf/RULES_REGISTRY.md - rule registry and codes</span></div>`;
  html += `<div class="ilink"><span class="il-rule">BENCH</span><span class="il-a">docs/upf/BENCHMARK_EVIDENCE_MAP.md - evidence suites</span></div>`;

  html += sectionTitle("UPF challenges", "why power intent is hard in real designs");
  [
    ["Multi-voltage designs", "Different blocks need different voltage levels; coordinating transitions between domains while preserving timing and signal integrity is complex.", "CHALLENGE"],
    ["Power domain interactions", "Domains interact during voltage scaling and state transitions; mishandling causes glitches, signal-integrity problems and higher power.", "CHALLENGE"],
    ["Advanced low-power techniques", "Body biasing, power gating and DVFS need precise control and coordination, and must stay backward compatible with the UPF framework.", "CHALLENGE"],
    ["EDA tool support", "Tools do not always interpret UPF constructs identically, so the same intent can behave differently across flows; intent must be explicit and verified.", "CHALLENGE"],
    ["System-level power management", "SoC power management is moving beyond single blocks toward cross-chip, multi-interface and heterogeneous coordination.", "FUTURE"],
    ["Energy harvesting integration", "Future UPF flows may fold harvested-energy sources into power-state decisions for autonomous, energy-efficient IoT-class devices.", "FUTURE"],
    ["Cross-disciplinary collaboration", "Power intent increasingly joins battery, thermal and system-architecture feedback so power decisions are made holistically.", "FUTURE"],
  ].forEach(([t, d, kind]) => html += `<div class="ilink"><span class="il-rule">${kind === "FUTURE" ? "→" : "△"}</span><span class="il-kind" style="color:${kind === "FUTURE" ? "var(--accent)" : "var(--warning)"}">${esc(kind)}</span><span class="il-a"><strong>${esc(t)}</strong> - ${esc(d)}</span></div>`);
  html += `<p class="callout co-info"><span><strong>Where UPF-Insight fits</strong> - the tool verifies the static power-intent half of these challenges (domains, supplies, states, isolation, retention, level shifters, strategies). Simulation, formal verification and implementation signoff remain separate EDA domains.</span></p>`;
  return html + "</div>";
}

/* ── Test Drive ─────────────────────────────────────────────────────────── */
export async function pageTestDrive() {
  let html = pageHead("TOOLS", "Test Drive",
    "Run the real UPF-Insight pipeline on believable samples - clean, buggy, design-aware, and a full V1→V2 regression workflow.",
    "Pick a scenario and press Analyze. Every result comes from the real backend, then follow the next actions.");
  html += `<div class="filters"><div class="f-field"><label>Scenario</label><select class="select-input" id="td-sample">
    <option value="good">Clean UPF - known-good 3-domain SoC</option>
    <option value="bad">Buggy UPF - undefined references</option>
    <option value="design">Design-aware - with netlist snapshot</option>
    <option value="regression">CPU regression - V1 known-good vs V2 regressed (validate → diff → gate)</option>
  </select></div><button class="btn btn-primary" id="td-run" type="button">Analyze sample</button>
  <button class="btn btn-sm" id="td-dl" type="button" disabled>Download results JSON</button></div>
  <div id="td-out"></div>`;
  return html + "</div>";
}

/* ── UPF Generator ──────────────────────────────────────────────────────── */
const GEN_GROUPS = {
  domains: {
    label: "Power domains", hint: "create_power_domain",
    fields: [
      { k: "name", label: "Name", w: 100, ph: "core" },
      { k: "elements", label: "Elements", w: 200, ph: "u_core u_ahb" },
      { k: "domain_type", label: "Type", w: 100, ph: "switchable" },
    ],
    defaults: [["core", "u_core", "switchable"], ["io", "u_io", ""], ["sram", "u_sram", "always_on"]],
  },
  relations: {
    label: "Domain relations", hint: "power-domain topology",
    fields: [
      { k: "from_domain", label: "From", w: 100, ph: "aon" },
      { k: "to_domain", label: "To", w: 100, ph: "core" },
      { k: "kinds", label: "Kinds", w: 220, ph: "switch,isolation,level_shift" },
    ],
    defaults: [["core", "io", "isolation,level_shift"], ["core", "sram", "isolation"]],
  },
  switches: {
    label: "Power switches", hint: "create_power_switch",
    fields: [
      { k: "name", label: "Name", w: 80, ph: "sw_core" },
      { k: "domain", label: "Domain", w: 60, ph: "core" },
      { k: "input_supply", label: "In port", w: 85, ph: "vdd_sw_in" },
      { k: "output_supply", label: "Out net", w: 85, ph: "vdd_sw_out" },
      { k: "control_port", label: "Control", w: 75, ph: "iso_ctrl" },
      { k: "on_state", label: "On state", w: 60, ph: "on" },
      { k: "off_state", label: "Off state", w: 60, ph: "off" },
    ],
    defaults: [["sw_core", "core", "vdd_sw_in", "vdd_sw_out", "iso_ctrl", "on", "off"]],
  },
  isolation: {
    label: "Isolation", hint: "set_isolation",
    fields: [
      { k: "domain", label: "Domain", w: 90, ph: "io" },
      { k: "clamp_value", label: "Clamp", w: 70, ph: "0" },
      { k: "isolation_supply", label: "Supply", w: 95, ph: "vdd_iso" },
      { k: "signal", label: "Signal", w: 90, ph: "iso_en" },
      { k: "location", label: "Location", w: 80, ph: "self" },
    ],
    defaults: [["io", "0", "vdd_iso", "iso_en", "self"]],
  },
  level_shifters: {
    label: "Level shifters", hint: "set_level_shifter",
    fields: [
      { k: "domain", label: "Domain", w: 100, ph: "io" },
      { k: "location", label: "Location", w: 85, ph: "self" },
      { k: "threshold", label: "Threshold", w: 80, ph: "0.8" },
      { k: "rule", label: "Rule", w: 120, ph: "low_to_high" },
    ],
    defaults: [["io", "self", "0.8", "low_to_high"]],
  },
  retention: {
    label: "Retention", hint: "set_retention",
    fields: [
      { k: "domain", label: "Domain", w: 100, ph: "core" },
      { k: "retention_supply", label: "Supply", w: 100, ph: "vdd_ret" },
      { k: "save_signal", label: "Save", w: 85, ph: "save" },
      { k: "restore_signal", label: "Restore", w: 95, ph: "restore" },
    ],
    defaults: [["core", "vdd_ret", "save", "restore"]],
  },
  repeaters: {
    label: "Repeaters", hint: "set_repeater",
    fields: [
      { k: "domain", label: "Domain", w: 100, ph: "io" },
      { k: "repeater_supply", label: "Supply", w: 100, ph: "vdd_rep" },
      { k: "signal", label: "Signal", w: 95, ph: "rep_en" },
      { k: "location", label: "Location", w: 85, ph: "self" },
      { k: "driver_type", label: "Driver", w: 110, ph: "minimal" },
    ],
    defaults: [["io", "vdd_rep", "rep_en", "self", "minimal"]],
  },
  pst_states: {
    label: "PST states", hint: "add_pst_state",
    fields: [
      { k: "name", label: "Name", w: 110, ph: "PS_ON" },
      { k: "states", label: "States", w: 360, ph: "vdd:ON vss:ON" },
    ],
    defaults: [
      ["PS_ON", "vdd:ON vss:ON"],
      ["PS_OFF", "vdd:OFF vss:ON"],
    ],
  },
};

function genRowsHtml(group, items) {
  const f = group.fields;
  return items.map(item => `<div class="gen-param-row">
    ${f.map((fd, i) => `<input class="opt-input gen-in" data-k="${fd.k}" style="width:${fd.w}px" placeholder="${fd.ph}" value="${esc(item[i] ?? "")}">`).join("")}
    <button class="icon-btn gen-del" type="button" title="Remove row">✕</button>
  </div>`).join("");
}

function genGroupPanelHtml(key) {
  const g = GEN_GROUPS[key];
  const head = `<span class="gen-glabel">${g.label}</span>
    <span class="mono gen-hint">${g.hint}</span>
    <button class="btn btn-sm gen-add" data-group="${key}" type="button">+ Add</button>`;
  const labels = `<div class="gen-head-row">${g.fields.map(fd => `<span class="opt-label" style="width:${fd.w}px">${fd.label}</span>`).join("")}<span class="opt-label" style="width:24px"></span></div>`;
  return `<div class="panel">
    <div class="panel-head">${head}</div>
    ${labels}
    <div class="gen-rows" data-group="${key}">${genRowsHtml(g, g.defaults)}</div>
  </div>`;
}

export function genEmptyRowHtml(key) {
  const g = GEN_GROUPS[key];
  return genRowsHtml(g, [g.fields.map(() => "")]);
}

export function genFieldKeys(key) {
  return GEN_GROUPS[key].fields.map(fd => fd.k);
}

export async function pageGenerator() {
  let html = pageHead("TOOLS", "UPF Generator",
    "Generate an IEEE 1801 power-intent file from parameters - domains, switches, isolation, level shifters, retention, repeaters and power states.",
    "Set the parameters, press Generate, then Validate the emitted UPF in place.");
  html += `<div class="input-surface">
    <div class="optional-panel" style="grid-template-columns:repeat(4,1fr)">
      <div><label class="opt-label" for="g-arch">Architecture</label><select class="opt-select" id="g-arch">
        <option value="flat">Flat</option><option value="hierarchical">Hierarchical</option></select></div>
      <div><label class="opt-label" for="g-hier">Hierarchy scopes</label><input class="opt-input" id="g-hier" value="" placeholder="core_a, core_b"></div>
      <div><label class="opt-label" for="g-top">Design top</label><input class="opt-input" id="g-top" value="top"></div>
      <div><label class="opt-label" for="g-ver">UPF version</label><select class="opt-select" id="g-ver">
        <option>3.0</option><option>2.1</option><option>4.0</option></select></div>
      <div><label class="opt-label" for="g-pp">Primary power</label><input class="opt-input" id="g-pp" value="vdd"></div>
      <div><label class="opt-label" for="g-pg">Primary ground</label><input class="opt-input" id="g-pg" value="vss"></div>
      <div><label class="opt-label" for="g-onv">On voltage (V)</label><input class="opt-input" id="g-onv" value="1.0"></div>
      <div><label class="opt-label" for="g-offv">Off voltage (V)</label><input class="opt-input" id="g-offv" value="0.0"></div>
      <div style="grid-column:1/-1"><label class="opt-label" for="g-aon">Always-on signals (comma-separated)</label><input class="opt-input" id="g-aon" value="clk, rst" style="width:100%"></div>
    </div>
    ${genGroupPanelHtml("domains")}
    ${genGroupPanelHtml("relations")}
    ${genGroupPanelHtml("switches")}
    ${genGroupPanelHtml("isolation")}
    ${genGroupPanelHtml("level_shifters")}
    ${genGroupPanelHtml("retention")}
    ${genGroupPanelHtml("repeaters")}
    ${genGroupPanelHtml("pst_states")}
    <div style="padding:10px 14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-top:1px solid var(--border-subtle)">
      <button class="btn btn-primary" id="g-gen" type="button">Generate</button>
      <button class="btn" id="g-validate" type="button">Validate</button>
      <button class="btn btn-sm" id="g-copy" type="button">Copy</button>
      <button class="btn btn-sm" id="g-dl" type="button">Download .upf</button>
      <span class="mono gen-status" id="g-status"></span>
    </div>
  </div>
  <div id="g-out"></div>
  <div id="g-val"></div>`;
  return html + "</div>";
}

/* ── UPF Diff (semantic, V1 vs V2) ──────────────────────────────────────── */
export async function pageDiff() {
  let html = pageHead("ADVANCED", "UPF Diff",
    "Compare two UPF power-intent files semantically - domains, supplies, switches, strategies and PST changes, not raw text.",
    "Paste Version A and Version B, then Compare. Identical semantics produce zero changes.");
  html += `<div class="input-surface entry">
    <div class="entry-step">
      <div class="es-num">1</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Version A - reference UPF</span><span class="es-req">REQUIRED</span></div>
        <div class="es-actions">
          <button class="btn btn-sm" id="df-pick-a" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="df-sample-a" type="button">Load sample V1</button>
          <span class="is-file mono" id="df-file-a">${esc(App.state.diffFileA || "pasted_a.upf")}</span>
        </div>
        <textarea class="code-input" id="df-a" rows="7" spellcheck="false" placeholder="upf_version 3.0&#10;set_design_top top&#10;create_power_domain core -elements {u_core}&#10;...">${esc(App.state.diffA || "")}</textarea>
      </div>
    </div>
    <div class="entry-step">
      <div class="es-num">2</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Version B - candidate UPF</span><span class="es-req">REQUIRED</span></div>
        <div class="es-actions">
          <button class="btn btn-sm" id="df-pick-b" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="df-sample-b" type="button">Load sample V2</button>
          <span class="is-file mono" id="df-file-b">${esc(App.state.diffFileB || "pasted_b.upf")}</span>
        </div>
        <textarea class="code-input" id="df-b" rows="7" spellcheck="false" placeholder="upf_version 3.0&#10;...">${esc(App.state.diffB || "")}</textarea>
      </div>
    </div>
  </div>
  <div class="entry-foot">
    <button class="btn btn-primary btn-lg" id="df-run" type="button">Compare</button>
    <span class="mono" style="font-size:11px;color:var(--text-muted)">semantic model diff · deterministic · offline</span>
  </div>
  <div id="df-out"></div>`;
  return html + "</div>";
}

/* ── CI Gate (policy evaluation) ────────────────────────────────────────── */
export async function pageGate() {
  let html = pageHead("ADVANCED", "CI Gate",
    "Gate a power-intent change against a policy - the same evaluation the CLI runs in CI, with PASS/FAIL, reasons and an exit code.",
    "Paste the candidate UPF, choose a policy, optionally supply a baseline, then Run Gate.");
  html += `<div class="input-surface entry">
    <div class="entry-step">
      <div class="es-num">1</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Candidate UPF</span><span class="es-req">REQUIRED</span></div>
        <div class="es-actions">
          <button class="btn btn-sm" id="gt-pick" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="gt-sample" type="button">Load sample V2 (regressed)</button>
          <button class="btn btn-sm btn-ghost" id="gt-use-current" type="button">Use current analysis</button>
          <span class="is-file mono" id="gt-file">${esc(App.state.filename)}</span>
        </div>
        <textarea class="code-input" id="gt-upf" rows="7" spellcheck="false" placeholder="upf_version 3.0&#10;...">${esc(App.state.gateUpf || "")}</textarea>
      </div>
    </div>
    <div class="entry-step">
      <div class="es-num">2</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Policy</span><span class="es-req">REQUIRED</span></div>
        <div class="filters" style="margin:0">
          <div class="f-field"><select class="select-input" id="gt-policy">
            <option value="BLOCKERS_ONLY">BLOCKERS_ONLY - fail on current blockers</option>
            <option value="NO_READINESS_REGRESSION">NO_READINESS_REGRESSION - fail on new blockers or trust regression vs baseline</option>
            <option value="STRICT" selected>STRICT - fail on blockers, review items, trust and coverage regressions</option>
          </select></div>
        </div>
      </div>
    </div>
    <div class="entry-step">
      <div class="es-num">3</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Baseline (optional)</span><span class="es-opt">OPTIONAL</span></div>
        <p class="es-why">Optional - without a baseline the gate evaluates the current evidence only. Paste a saved result JSON, or run against the current analysis as baseline.</p>
        <div class="es-actions">
          <button class="btn btn-sm btn-ghost" id="gt-base-current" type="button">Set baseline = current analysis</button>
        </div>
        <textarea class="opt-text" id="gt-baseline" rows="3" spellcheck="false" placeholder='{"check": {...}, "readiness": {...}, ...} - a saved result'></textarea>
      </div>
    </div>
  </div>
  <div class="entry-foot">
    <button class="btn btn-primary btn-lg" id="gt-run" type="button">Run Gate</button>
    <span class="mono" style="font-size:11px;color:var(--text-muted)">exit 0 PASS · 1 FAIL · 2 invalid · 3 engine failure</span>
  </div>
  <div id="gt-out"></div>`;
  return html + "</div>";
}

/* ── Reports (real evidence) ────────────────────────────────────────────── */
export async function pageReports() {
  let html = pageHead("OUTPUT & KNOWLEDGE", "Reports",
    "Generate reports from real analysis evidence - findings, rule IDs, source lines, readiness, coverage and the support boundary.",
    "Paste UPF, choose a format, then Generate. Reports contain real engine output, never placeholders.");
  html += `<div class="input-surface entry">
    <div class="entry-step">
      <div class="es-num">1</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">UPF to report</span><span class="es-req">REQUIRED</span></div>
        <div class="es-actions">
          <button class="btn btn-sm" id="rp-pick" type="button">Choose file…</button>
          <button class="btn btn-sm btn-ghost" id="rp-sample" type="button">Load sample V2</button>
          <button class="btn btn-sm btn-ghost" id="rp-use-current" type="button">Use current analysis</button>
          <span class="is-file mono" id="rp-file">${esc(App.state.filename)}</span>
        </div>
        <textarea class="code-input" id="rp-upf" rows="6" spellcheck="false" placeholder="upf_version 3.0&#10;...">${esc(App.state.reportUpf || "")}</textarea>
        <div class="optional-panel">
          <div>
            <label class="opt-label" for="rp-netlist">Design context (JSON, optional)</label>
            <textarea class="opt-text" id="rp-netlist" rows="2" spellcheck="false" placeholder='{"instances": {...}, "ports": [...], ...}'></textarea>
          </div>
        </div>
      </div>
    </div>
    <div class="entry-step">
      <div class="es-num">2</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Format</span><span class="es-req">REQUIRED</span></div>
        <div class="filters" style="margin:0">
          <div class="f-field"><select class="select-input" id="rp-format">
            <option value="html" selected>HTML - human-readable report</option>
            <option value="json">JSON - machine-readable evidence</option>
            <option value="text">Text - terminal-friendly</option>
          </select></div>
        </div>
      </div>
    </div>
  </div>
  <div class="entry-foot">
    <button class="btn btn-primary btn-lg" id="rp-run" type="button">Generate Report</button>
    <span class="mono" style="font-size:11px;color:var(--text-muted)">real findings · rule IDs · lines · readiness · support</span>
  </div>
  <div id="rp-out"></div>`;
  return html + "</div>";
}

/* ═══════════════════════════════════════════════════════════════════════════
   Page registry + event wiring
   ═══════════════════════════════════════════════════════════════════════════ */

/* One canonical feature order everywhere (home cards, nav, palette):
   CORE → ANALYZE → ADVANCED → OUTPUT/KNOWLEDGE. Every feature owns its
   input surface and is always visible - standalone first. */
export const PAGES = {
  home: { label: "Home", render: pageHome, group: "WORKSPACE" },
  new_analysis: { label: "New Analysis", render: pageNewAnalysis, group: "WORKSPACE" },
  validator: { label: "Validation", render: pageValidator, group: "CORE" },
  generator: { label: "Generator", render: pageGenerator, group: "CORE" },
  pst: { label: "Power States", render: pagePST, group: "ANALYZE" },
  supply: { label: "Supply Network", render: pageSupply, group: "ANALYZE" },
  strategies: { label: "Strategies", render: pageStrategies, group: "ANALYZE" },
  relations: { label: "Domain Relations", render: pageRelations, group: "ANALYZE" },
  design: { label: "Design", render: pageDesign, group: "ANALYZE" },
  coverage: { label: "Coverage", render: pageCoverage, group: "ANALYZE" },
  readiness: { label: "Health", render: pageReadiness, group: "ANALYZE" },
  diff: { label: "UPF Diff", render: pageDiff, group: "ADVANCED" },
  gate: { label: "CI Gate", render: pageGate, group: "ADVANCED" },
  test_drive: { label: "Test Drive", render: pageTestDrive, group: "ADVANCED" },
  reports: { label: "Reports", render: pageReports, group: "OUTPUT" },
  rules: { label: "Rules", render: pageRules, group: "OUTPUT" },
  trust: { label: "Trust", render: pageTrust, group: "OUTPUT" },
  documentation: { label: "Documentation", render: pageDocumentation, group: "OUTPUT" },
  overview: { label: "Summary", render: pageOverview, group: "RESULTS" },
  support: { label: "Support", render: pageSupport, group: "RESULTS" },
  export: { label: "Export", render: pageExport, group: "RESULTS" },
};

const GROUP_ORDER = ["WORKSPACE", "CORE", "ANALYZE", "ADVANCED", "OUTPUT", "RESULTS"];

function navItemHtml(view, label, current) {
  const active = view === current ? " active" : "";
  return `<button class="nav-item${active}" data-view="${view}" role="tab" aria-selected="${view === current}">
    <span class="ni-icon">${iconFor(view)}</span><span>${label}</span>
  </button>`;
}

export function navGroupsHtml(current) {
  const byGroup = {};
  Object.entries(PAGES).forEach(([id, p]) => {
    (byGroup[p.group] = byGroup[p.group] || []).push([id, p.label]);
  });
  return GROUP_ORDER.map(group => {
    const items = byGroup[group] || [];
    if (!items.length) return "";
    return `<div class="nav-group"><span class="nav-group-label">${group}</span>${items.map(([id, l]) => navItemHtml(id, l, current)).join("")}</div>`;
  }).join("");
}

function iconFor(id) {
  const I = {
    home: "◈", new_analysis: "＋", validator: "◈", supply: "▤", pst: "◫",
    strategies: "⇄", coverage: "▦", readiness: "◫", design: "▤", support: "◇",
    export: "⇩", rules: "☰", trust: "◆", documentation: "❐", test_drive: "▶",
    generator: "❐", diff: "⇄", gate: "⌦", reports: "❐",
  };
  return I[id] || "·";
}

export { findingObj, findingLoc, locLines };
