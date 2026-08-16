/* ═══════════════════════════════════════════════════════════════════════════
   UPF-Insight — pages.js
   All workspace page renderers. Every page consumes REAL backend evidence
   through the API — no mock data, no invented counts. All user-controlled
   content is escaped via theme.esc. Mirrors the Ṛta pages.js structure.
   ═══════════════════════════════════════════════════════════════════════════ */

import { esc, statusBadge, severityClass } from "./theme.js";
import { pageHead, sectionTitle, metricRow, chips, emptyState, typedError,
         callout, sourceViewer, sourceExcerpt, table, accordion, kvList,
         segFilter, findingRow, findingDetailHtml } from "./components.js";
import { readinessRail, supplyStripHtml, pstMatrixHtml } from "./viz.js";

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

/* ── Overview (Summary) ─────────────────────────────────────────────────── */
export async function pageOverview() {
  const a = App.state.analysis;
  if (!a) {
    return pageHead("RESULTS", "Summary", "Run an analysis first — the summary is built from real analysis evidence.",
      "Open New Analysis, load a UPF file, then press Analyze.")
      + emptyState("No analysis yet", "Run a validation on a UPF file to populate the overview.",
                   "Open New Analysis, load a UPF file, then press Analyze.");
  }
  const rdy = a.readiness || {};
  const c = a.check || {};
  const counts = c.counts || {};
  const m = a.model || {};
  const cov = a.coverage || {};
  const blockers = (rdy.blockers || []).slice(0, 8);

  let html = pageHead("RESULTS", "Summary", "The executive view — verdict, trust, power intent, coverage.",
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
    html += sectionTitle("Coverage", "what the intent touches — coverage ≠ correctness");
    html += metricRow([
      { label: "Domain coverage", value: Math.round(cov.domain_coverage * 100) + "%" },
      { label: "Supply coverage", value: Math.round(cov.supply_coverage * 100) + "%" },
      { label: "Unreferenced supplies", value: (cov.unreferenced_supplies || []).length },
    ]);
    html += `<p class="callout co-info" style="margin-top:6px"><span><strong>Coverage is not correctness</strong> — a fully covered design can still have power-intent errors.</span></p>`;
  }

  (rdy.notes || []).forEach(n => html += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">— ${esc(n)}</div>`);
  html += `<p class="callout co-warning" style="margin-top:16px"><span><strong>READY ≠ signoff</strong> — this is a power-intent review, not a power/IR signoff.</span></p>`;
  return html + "</div>";
}

/* ── Home dashboard (landing) ───────────────────────────────────────────── */
function capCard(icon, title, desc, meta, view, cta) {
  return `<div class="cap-card">
    <div class="cap-head"><span class="cap-icon">${icon}</span><span class="cap-title">${esc(title)}</span></div>
    <p class="cap-desc">${esc(desc)}</p>
    <div class="cap-meta">${meta.map(([k, v]) =>
      `<div class="cap-kv"><span class="cap-k">${esc(k)}</span><span class="cap-v">${esc(v)}</span></div>`).join("")}
    </div>
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
       "Check IEEE 1801 power intent across syntax, references, supply/domain, PST, strategy and design-aware layers — every finding traces to a rule and a source line.",
       [["Input", "UPF (required) · design JSON (optional)"],
        ["Does", "deterministic 6-layer check"],
        ["Get", "findings with rule links + source lines"],
        ["Next", "Findings · Coverage · Health"]],
       "validator", "Open Validation"),
      capCard("❐", "UPF Generator",
       "Build standard IEEE 1801 constructs — power domains, supply switches, isolation, level shifters, retention, repeaters, PST states — into a reviewable UPF file, then validate it in place.",
       [["Input", "domain / switch / isolation / LS / retention params"],
        ["Does", "emit IEEE 1801 constructs · inline validate"],
        ["Get", "UPF text · 0E / 0W confirmation"],
        ["Next", "Validate generated UPF"]],
       "generator", "Open Generator"),
    ],
    analyze: [
      capCard("◫", "Power State Intelligence",
       "Declared supply states, the Power State Table, and cross-state legality — every valid and missing state combination in one matrix.",
       [["Input", "create_pst · add_pst_state · add_port_state"],
        ["Does", "build PST matrix · state legality"],
        ["Get", "state matrix · per-state supplies"],
        ["Next", "Supply Network"]],
       "pst", "Open Power States"),
      capCard("▤", "Supply Network",
       "Power domains, supply ports/nets/sets, and power switches behind the intent — the structural supply picture.",
       [["Input", "create_power_domain · create_supply_* · create_power_switch"],
        ["Does", "domain + supply + switch inventory"],
        ["Get", "network tables with scope and functions"],
        ["Next", "Coverage"]],
       "supply", "Open Supply Network"),
      capCard("⇄", "Strategies",
       "Isolation, retention, and level-shifter strategies declared in the intent — location, clamp, control and supply.",
       [["Input", "set_isolation · set_retention · set_level_shifter"],
        ["Does", "strategy inventory + conditioning"],
        ["Get", "strategy tables per strategy kind"],
        ["Next", "Design Context"]],
       "strategies", "Open Strategies"),
      capCard("▤", "Design Context",
       "Design-aware layer (UPF-080…084) cross-checks power intent against a netlist snapshot — instances, ports, PG pins, sequential state.",
       [["Input", "netlist JSON (instances / ports / PG pins)"],
        ["Does", "netlist cross-checks · UPF-080…084 rules"],
        ["Get", "netlist-grounded findings"],
        ["Next", "Findings"]],
       "design", "Open Design"),
      capCard("▦", "Coverage",
       "Is every power domain and supply accounted for? Coverage reports what the intent touches — coverage is not correctness.",
       [["Input", "full analysis result"],
        ["Does", "domain + supply coverage"],
        ["Get", "coverage % · gaps · unreferenced supplies"],
        ["Next", "Health"]],
       "coverage", "Open Coverage"),
      capCard("◫", "Readiness",
       "Verdict, blockers, review items and advisories across five dimensions — READY is not a power/IR signoff.",
       [["Input", "full analysis result"],
        ["Does", "5-dimension readiness with reasons"],
        ["Get", "verdict · blockers · why"],
        ["Next", "Support boundary"]],
       "readiness", "Open Health"),
    ],
    advanced: [
      capCard("⇄", "UPF Diff",
       "Compare two UPF revisions semantically — domains, supplies, switches, strategies and PST changes — not raw text.",
       [["Input", "Version A UPF · Version B UPF"],
        ["Does", "model-level semantic comparison"],
        ["Get", "ADD / REMOVE / MODIFY changes"],
        ["Next", "Validate · CI Gate"]],
       "diff", "Open Diff"),
      capCard("⌦", "CI Gate",
       "Gate power-intent changes against a policy — PASS/FAIL with reasons and an exit code, exactly as CI would see it.",
       [["Input", "UPF · policy · optional baseline"],
        ["Does", "policy evaluation (BLOCKERS_ONLY / NO_READINESS_REGRESSION / STRICT)"],
        ["Get", "PASS / FAIL · reasons · JSON"],
        ["Next", "Reports"]],
       "gate", "Open CI Gate"),
      capCard("▶", "Test Drive",
       "Run the real workflow on believable samples — clean, buggy, and a V1→V2 regression — validate, diff and gate.",
       [["Input", "built-in samples (clean / buggy / regression)"],
        ["Does", "real backend analysis end-to-end"],
        ["Get", "findings · diff · gate result"],
        ["Next", "Findings"]],
       "test_drive", "Start Test Drive"),
    ],
    output: [
      capCard("❐", "Reports",
       "HTML / JSON / text reports generated from real analysis evidence — findings, rule IDs, lines, readiness and support.",
       [["Input", "UPF (or current analysis)"],
        ["Does", "report generation (html / json / text)"],
        ["Get", "downloadable report with real evidence"],
        ["Next", "Trust"]],
       "reports", "Open Reports"),
      capCard("☰", "Rules",
       `Browse ${_RULE_COUNT()} deterministic rules across six layers — what each detects, its severity, and why it matters.`,
       [["Input", "none — reference surface"],
        ["Does", "rule registry browse"],
        ["Get", "rule ID · severity · description"],
        ["Next", "Documentation"]],
       "rules", "Open Rules"),
      capCard("◆", "Trust",
       "What UPF-Insight validates, partially validates, and never claims — the trust boundary, plainly.",
       [["Input", "none — disclosure surface"],
        ["Does", "boundary statements"],
        ["Get", "trust model + limitations"],
        ["Next", "Support boundary"]],
       "trust", "Open Trust"),
      capCard("❐", "Documentation",
       "Repository documentation, CLI reference, and the evidence map — the UPF journey from zero to result.",
       [["Input", "none — reference surface"],
        ["Does", "link real repository docs"],
        ["Get", "quick-start + references"],
        ["Next", "Rules"]],
       "documentation", "Open Documentation"),
    ],
  };
  let html = pageHead("UPF-INSIGHT", "What can I do with UPF-Insight?",
    "UPF-Insight runs a deterministic, local analysis of IEEE 1801 power intent — validation, PST intelligence, supply/strategy analysis, design-aware cross-checks, semantic diff, a CI gate, and reports.");
  html += `<div class="hero">
    <div class="hero-actions">
      <button class="btn btn-primary" type="button" data-home-view="test_drive">Start with Test Drive</button>
      <button class="btn btn-primary" type="button" data-home-view="new_analysis">Validate a UPF</button>
      <button class="btn btn-primary" type="button" data-home-view="gate">Run CI Gate</button>
    </div>
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
    "Drop in your UPF (IEEE 1801) file — UPF-Insight runs a deterministic check across syntax, references, supply/domain, PST, strategy and design-aware layers.",
    has ? "Analysis loaded — load a new UPF to re-run, or explore the results."
        : "The sample is loaded — press Analyze, or load your own UPF.");
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
        <p class="es-why">Optional — UPF-only mode validates syntax, references, supply/domain, PST and strategy layers without design context. Adding a design snapshot unlocks the design-aware layer (UPF-080…084).</p>
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
  html += chips([statusBadge("trust", trustFromSupport(a.support)), statusBadge("readiness", (a.readiness || {}).overall || "—")]);

  html += metricRow([
    { label: "Errors", value: errs }, { label: "Warnings", value: warns },
    { label: "Info", value: infos }, { label: "Commands", value: a.command_count ?? 0 },
  ]);

  if (errs) html += callout(`${errs} error(s) must be reviewed before implementation. A clean check is not a power/IR signoff.`, "error");
  else if (warns) html += callout(`No errors — ${warns} warning(s) need review.`, "warning");
  else html += callout("No errors or warnings within scope. See the support boundary for what was verified — this is not a power/IR signoff.", "info");

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

  if (!issues.length) html += emptyState("No issues found", "No findings within the supported analysis scope.", "Review the support boundary — a clean check is not a power/IR signoff.");
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
    html += `<div style="margin-top:10px">`;
    html += filtered.slice(0, 12).map(it => accordion(`${it.code} — ${it.msg.length > 80 ? it.msg.slice(0, 80) + "…" : it.msg}`,
      findingDetailHtml(it, App.state.rules ? App.state.rules.find(r => r.code === it.code) : null)
      + sourceExcerpt(App.state.upf.split("\n"), locLines(it)), {})).join("");
    if (filtered.length > 12) html += `<div class="mono" style="font-size:11px;color:var(--text-muted)">… ${filtered.length - 12} more details; all findings are in the table above.</div>`;
    html += `</div>`;
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
  (rdy.notes || []).forEach(n => h += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">— ${esc(n)}</div>`);
  h += `<p class="callout co-warning"><span><strong>READY ≠ signoff</strong> — this is a power-intent review, not a power/IR signoff.</span></p>`;
  return h;
}

function renderCoverage(a) {
  const cov = a.coverage || {};
  if (cov.domain_coverage === undefined && !(cov.domains || []).length) return "";
  let h = sectionTitle("Power-intent coverage", "what the intent touches");
  h += `<p class="callout co-info"><span><strong>Coverage is NOT correctness</strong> — a fully covered design can still have power-intent errors.</span></p>`;
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
  (sup.notes || []).forEach(n => h += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">— ${esc(n)}</div>`);
  h += `<p class="callout co-info"><span><strong>Deterministic engine</strong> — no LLM, no model inference. Analysis is local, reproducible and offline-capable.</span></p>`;
  return h;
}

/* ── Supply Network ─────────────────────────────────────────────────────── */
export async function pageSupply() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Supply Network", "Domains, supply ports/nets/sets and power switches behind your power intent.");
  if (!a || !a.model) {
    html += emptyState("No supply network yet", "Run a validation first.", "Open New Analysis and press Analyze.");
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
        { html: `<span class="mono">${esc(s.name)}</span>` }, esc(s.input_supply || "—"), esc(s.output_supply || "—"),
        esc(s.control_port || "—"), esc(s.on_state || "—"),
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
  let html = pageHead("RESULTS", "Power States", "Declared supply states and the Power State Table (PST) rows.");
  if (!a) {
    html += emptyState("No power states yet", "Run a validation first.", "Open New Analysis and press Analyze.");
    return html + "</div>";
  }
  const pst = a.pst || {};
  const m = a.model || {};
  const states = (m.supply_states || []);
  html += metricRow([
    { label: "PST", value: pst.pst_name || "—" }, { label: "PST states", value: pst.state_count ?? 0 },
    { label: "Declared states", value: (pst.declared_supply_states || []).length },
    { label: "Used", value: (pst.used_supply_states || []).length },
    { label: "Unused", value: (pst.unused_states || []).length },
    { label: "Undeclared", value: (pst.undeclared_states || []).length },
  ]);
  if (pst.coverage_note) html += `<p class="callout ${pst.undeclared_states && pst.undeclared_states.length ? "co-warning" : "co-info"}"><span><strong>Coverage</strong> — ${esc(pst.coverage_note)}</span></p>`;

  if (states.length) {
    html += sectionTitle("Declared supply states", `${states.length} state(s)`);
    html += table([{ label: "State" }, { label: "Parent" }, { label: "Type" }, { label: "Voltage" }],
      states.map(s => ({ key: s.name + (s.parent || ""), cells: [
        { html: `<span class="mono">${esc(s.name)}</span>` }, esc(s.parent || "—"), esc(s.type || "supply_state"),
        { html: `<span class="num">${s.voltage != null ? esc(s.voltage) + " V" : "—"}</span>` },
      ] })));
  }

  if (Object.keys(m.psts || {}).length) {
    html += sectionTitle("PST rows");
    Object.values(m.psts || {}).forEach(p => {
      html += pstMatrixHtml(p);
    });
    html += sectionTitle("Transitions");
    html += `<div class="mono" style="font-size:12px;color:var(--text-secondary)">${esc((pst.transitions || []).map(t => `${t[0]} → ${t[1]}`).join(" · ") || "—")}</div>`;
  }
  return html + "</div>";
}

/* ── Strategies ─────────────────────────────────────────────────────────── */
export async function pageStrategies() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Strategies", "Isolation, retention and level-shifter strategies in your power intent.");
  if (!a || !a.model) {
    html += emptyState("No strategies yet", "Run a validation first.", "Open New Analysis and press Analyze.");
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
        { html: `<span class="mono">${esc(s.domain)}</span>` }, esc(s.location || "self"), esc(s.clamp_value || "—"),
        esc(s.applies_to || "outputs"), esc(s.control_signal || "—"), esc(s.isolation_supply || "—"),
      ] })));
  }
  if ((m.level_shifters || []).length) {
    html += sectionTitle("Level shifters", `${(m.level_shifters || []).length} strategy(ies)`);
    html += table([{ label: "Domain" }, { label: "Location" }, { label: "Rule" }, { label: "Threshold" }],
      m.level_shifters.map(s => ({ key: s.domain, cells: [
        { html: `<span class="mono">${esc(s.domain)}</span>` }, esc(s.location || "self"), esc(s.rule || "low_to_high"),
        { html: `<span class="num">${s.threshold != null ? esc(s.threshold) : "—"}</span>` },
      ] })));
  }
  if ((m.retentions || []).length) {
    html += sectionTitle("Retention", `${(m.retentions || []).length} strategy(ies)`);
    html += table([{ label: "Domain" }, { label: "Supply" }, { label: "Save" }, { label: "Restore" }],
      m.retentions.map(s => ({ key: s.domain, cells: [
        { html: `<span class="mono">${esc(s.domain)}</span>` }, esc(s.retention_supply || "—"), esc(s.save_signal || "—"), esc(s.restore_signal || "—"),
      ] })));
  }
  return html + "</div>";
}

/* ── Design context ─────────────────────────────────────────────────────── */
export async function pageDesign() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Design", "The netlist snapshot behind your design-aware rules (UPF-080…084).",
                      "Add a design context JSON in New Analysis to unlock the design-aware layer.");
  if (!a) {
    html += emptyState("No design context", "Add a design snapshot to enable the design-aware layer.", "Open New Analysis, paste a design JSON, and re-analyze.");
    return html + "</div>";
  }
  const design = (a.model || {}).design;
  if (!design) {
    html += emptyState("Design context not supplied", "The design-aware layer (UPF-080…084) is silent without a design snapshot.", "Add the design JSON in New Analysis and re-analyze.");
    return html + "</div>";
  }
  html += `<p class="callout co-info"><span><strong>Design-aware rules active</strong> — UPF-080…084 validate instances, control signals, crossings, retention coverage and PG pins against this snapshot.</span></p>`;
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
        { html: `<span class="mono">${esc(inst[n].module || "—")}</span>` },
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
                      "A fully covered design is not a correct design — review the evidence.");
  if (!a || !a.coverage || a.coverage.domain_coverage === undefined) {
    html += emptyState("No coverage yet", "Run a validation first.", "Open New Analysis and press Analyze.");
    return html + "</div>";
  }
  const cov = a.coverage;
  html += `<p class="callout co-info"><span><strong>Coverage is NOT correctness</strong> — coverage reports what the intent touches, never that it is right.</span></p>`;
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
    html += `<p class="callout co-success"><span><strong>All declared supplies are referenced</strong> — no unreferenced supplies.</span></p>`;
  }
  return html + "</div>";
}

/* ── Readiness (Health) ─────────────────────────────────────────────────── */
export async function pageReadiness() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Health", "Is this power intent ready to hand to implementation?",
                      "Resolve blockers first, then review items — READY is not a signoff.");
  if (!a || !a.readiness || !a.readiness.overall) {
    html += emptyState("No readiness yet", "Run a validation first.", "Open New Analysis and press Analyze.");
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
  (rdy.notes || []).forEach(n => html += `<div class="mono" style="font-size:11.5px;color:var(--text-muted)">— ${esc(n)}</div>`);
  html += `<p class="callout co-warning"><span><strong>READY ≠ signoff</strong> — READY means no rule fired within the supported scope. It is not a power/IR signoff.</span></p>`;
  return html + "</div>";
}

/* ── Support / Trust boundary ───────────────────────────────────────────── */
export async function pageSupport() {
  const a = App.state.analysis;
  let html = pageHead("RESULTS", "Support", "What UPF-Insight validated, partially validated, and skipped.",
                      "A clean result means 'no rule fired', never 'power intent proven correct'.");
  if (!a || !a.support) {
    html += emptyState("No support boundary yet", "Run a validation first.", "Open New Analysis and press Analyze.");
    return html + "</div>";
  }
  const sup = a.support;
  html += `<div class="chips">${statusBadge("trust", trustFromSupport(sup))}</div>`;
  html += sectionTitle("Boundary counts");
  html += metricRow(
    Object.entries(sup.statuses || {}).map(([k, v]) => ({ label: k.replace(/_/g, " "), value: v }))
  );
  (sup.notes || []).forEach(n => html += `<div class="ilink"><span class="il-rule">NOTE</span><span class="il-a">${esc(n)}</span></div>`);
  html += `<p class="callout co-info"><span><strong>Deterministic engine</strong> — no LLM, no model inference, no external AI APIs. Local, reproducible, offline-capable.</span></p>`;
  return html + "</div>";
}

/* ── Rules ──────────────────────────────────────────────────────────────── */
export async function pageRules() {
  let html = pageHead("TOOLS", "Rules Registry", `${App.state.rules ? App.state.rules.length : "…"} deterministic rules across six layers.`);
  if (!App.state.rules) {
    try { App.state.rules = (await get("/api/rules")).rules || []; }
    catch (e) { App.state.rules = []; }
    html = pageHead("TOOLS", "Rules Registry", `${App.state.rules.length} deterministic rules across six layers.`);
  }
  const sev = App.state.ruleFilter || "All";
  const rules = sev === "All" ? App.state.rules : App.state.rules.filter(r => r.severity === sev);
  html += `<div class="filters"><div class="f-field"><label>Severity</label>${segFilter("rule-sev", ["All", "error", "warning", "info"], sev)}</div></div>`;
  const byLayer = {};
  rules.forEach(r => (byLayer[r.layer] = byLayer[r.layer] || []).push(r));
  Object.entries(byLayer).forEach(([layer, rs]) => {
    html += sectionTitle(layer, `${rs.length} rule(s)`);
    rs.forEach(r => {
      html += `<div class="rule-row"><span class="rule-code">${esc(r.code)}</span> <span class="rule-name">${esc(r.title)}</span> ${statusBadge("severity", r.severity)}<div class="rule-desc">${esc(r.description)}</div></div>`;
    });
  });
  return html + "</div>";
}

/* ── Export ─────────────────────────────────────────────────────────────── */
export async function pageExport() {
  let html = pageHead("RESULTS", "Export", "Real exportable evidence — JSON result, readiness snapshot (CLI).");
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
    ["READY ≠ SIGNOFF", "READY means the power intent satisfies the validator's supported, evidence-backed criteria — not that power/IR or timing passes."],
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
  html += `<p class="callout co-info"><span><strong>Deterministic engine</strong> — no LLM, no model inference, no external AI APIs. Analysis is local, reproducible and offline-capable.</span></p>`;
  return html + "</div>";
}

/* ── Documentation ──────────────────────────────────────────────────────── */
export async function pageDocumentation() {
  let html = pageHead("TOOLS", "Documentation", "Repository documentation, CLI reference and evidence — real entries only.");
  const rules = App.state.rules;
  html += `<div class="kv" style="margin:8px 0">`;
  html += `<dt>Engine</dt><dd class="mono">deterministic · local-first · offline-capable</dd>`;
  html += `<dt>Rules</dt><dd class="mono">${rules ? rules.length + " deterministic rules across six layers" : "loaded on demand"}</dd>`;
  html += `<dt>CLI</dt><dd class="mono">upf-insight check · model · pst · report · web</dd>`;
  html += `</div>`;
  html += sectionTitle("Reference");
  html += `<div class="ilink"><span class="il-rule">ROOT</span><span class="il-a">README.md — product overview and quick start</span></div>`;
  html += `<div class="ilink"><span class="il-rule">RULES</span><span class="il-a">docs/upf/RULES_REGISTRY.md — rule registry and codes</span></div>`;
  html += `<div class="ilink"><span class="il-rule">BENCH</span><span class="il-a">docs/upf/BENCHMARK_EVIDENCE_MAP.md — evidence suites</span></div>`;
  return html + "</div>";
}

/* ── Test Drive ─────────────────────────────────────────────────────────── */
export async function pageTestDrive() {
  let html = pageHead("TOOLS", "Test Drive",
    "Run the real UPF-Insight pipeline on believable samples — clean, buggy, design-aware, and a full V1→V2 regression workflow.",
    "Pick a scenario and press Analyze. Every result comes from the real backend, then follow the next actions.");
  html += `<div class="filters"><div class="f-field"><label>Scenario</label><select class="select-input" id="td-sample">
    <option value="good">Clean UPF — known-good 3-domain SoC</option>
    <option value="bad">Buggy UPF — undefined references</option>
    <option value="design">Design-aware — with netlist snapshot</option>
    <option value="regression">CPU regression — V1 known-good vs V2 regressed (validate → diff → gate)</option>
  </select></div><button class="btn btn-primary" id="td-run" type="button">Analyze sample</button></div>
  <div id="td-out"></div>`;
  return html + "</div>";
}

/* ── UPF Generator ──────────────────────────────────────────────────────── */
const GEN_GROUPS = {
  domains: {
    label: "Power domains", hint: "create_power_domain",
    fields: [
      { k: "name", label: "Name", w: 120, ph: "core" },
      { k: "elements", label: "Elements", w: 240, ph: "u_core u_ahb" },
    ],
    defaults: [["core", ""], ["io", ""], ["sram", ""]],
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
    "Build standard IEEE 1801 power-intent constructs — domains, supply switches, isolation, level shifters, retention, repeaters, PST states — into a reviewable UPF file.",
    "Set parameters, press Generate, then Validate to check the emitted UPF in place.");
  html += `<div class="gen-grid">
    <div class="gen-params">
      <div class="panel">
        <div class="panel-head"><span class="gen-glabel">Design</span><span class="mono gen-hint">set_design_top</span></div>
        <div class="gen-param-row">
          <label class="opt-label">Design top</label>
          <input class="opt-input gen-in" id="g-top" value="top" style="width:140px">
          <label class="opt-label">UPF version</label>
          <select class="opt-select gen-in" id="g-ver" style="width:80px">
            <option>3.0</option><option>2.1</option><option>4.0</option>
          </select>
        </div>
        <div class="gen-param-row">
          <label class="opt-label">Power</label><input class="opt-input gen-in" id="g-pp" value="vdd" style="width:80px">
          <label class="opt-label">Ground</label><input class="opt-input gen-in" id="g-pg" value="vss" style="width:80px">
          <label class="opt-label">On V</label><input class="opt-input gen-in" id="g-onv" value="1.0" style="width:60px">
          <label class="opt-label">Off V</label><input class="opt-input gen-in" id="g-offv" value="0.0" style="width:60px">
        </div>
      </div>
      ${genGroupPanelHtml("domains")}
      ${genGroupPanelHtml("switches")}
      ${genGroupPanelHtml("isolation")}
      ${genGroupPanelHtml("level_shifters")}
      ${genGroupPanelHtml("retention")}
      ${genGroupPanelHtml("repeaters")}
      ${genGroupPanelHtml("pst_states")}
      <div class="panel">
        <div class="panel-head"><span class="gen-glabel">Always-on signals</span><span class="mono gen-hint">set_port_attributes</span></div>
        <input class="opt-input gen-in" id="g-aon" value="clk, rst" style="width:100%">
      </div>
    </div>
    <div class="gen-out">
      <div class="toolbar">
        <button class="btn btn-primary btn-sm" id="g-gen" type="button">Generate</button>
        <button class="btn btn-sm" id="g-validate" type="button">Validate</button>
        <button class="btn btn-sm" id="g-copy" type="button">Copy</button>
        <button class="btn btn-sm" id="g-dl" type="button">Download .upf</button>
        <span class="mono gen-status" id="g-status"></span>
      </div>
      <div id="g-out"></div>
      <div id="g-val"></div>
    </div>
  </div>`;
  return html + "</div>";
}

/* ── UPF Diff (semantic, V1 vs V2) ──────────────────────────────────────── */
export async function pageDiff() {
  let html = pageHead("ADVANCED", "UPF Diff",
    "Compare two UPF power-intent files semantically — domains, supplies, switches, strategies and PST changes, not raw text.",
    "Paste Version A and Version B, then Compare. Identical semantics produce zero changes.");
  html += `<div class="input-surface entry">
    <div class="entry-step">
      <div class="es-num">1</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Version A — reference UPF</span><span class="es-req">REQUIRED</span></div>
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
        <div class="es-head"><span class="es-title">Version B — candidate UPF</span><span class="es-req">REQUIRED</span></div>
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
    "Gate a power-intent change against a policy — the same evaluation the CLI runs in CI, with PASS/FAIL, reasons and an exit code.",
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
            <option value="BLOCKERS_ONLY">BLOCKERS_ONLY — fail on current blockers</option>
            <option value="NO_READINESS_REGRESSION">NO_READINESS_REGRESSION — fail on new blockers or trust regression vs baseline</option>
            <option value="STRICT" selected>STRICT — fail on blockers, review items, trust and coverage regressions</option>
          </select></div>
        </div>
      </div>
    </div>
    <div class="entry-step">
      <div class="es-num">3</div>
      <div class="es-main">
        <div class="es-head"><span class="es-title">Baseline (optional)</span><span class="es-opt">OPTIONAL</span></div>
        <p class="es-why">Optional — without a baseline the gate evaluates the current evidence only. Paste a saved result JSON, or run against the current analysis as baseline.</p>
        <div class="es-actions">
          <button class="btn btn-sm btn-ghost" id="gt-base-current" type="button">Set baseline = current analysis</button>
        </div>
        <textarea class="opt-text" id="gt-baseline" rows="3" spellcheck="false" placeholder='{"check": {...}, "readiness": {...}, ...} — a saved result'></textarea>
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
    "Generate reports from real analysis evidence — findings, rule IDs, source lines, readiness, coverage and the support boundary.",
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
            <option value="html" selected>HTML — human-readable report</option>
            <option value="json">JSON — machine-readable evidence</option>
            <option value="text">Text — terminal-friendly</option>
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

export const PAGES = {
  // WORKSPACE — always available; every tool owns its input surface.
  home: { label: "Home", render: pageHome, group: "WORKSPACE" },
  new_analysis: { label: "New Analysis", render: pageNewAnalysis, group: "WORKSPACE" },
  validator: { label: "Validation", render: pageValidator, group: "WORKSPACE" },
  generator: { label: "Generator", render: pageGenerator, group: "WORKSPACE" },
  diff: { label: "UPF Diff", render: pageDiff, group: "WORKSPACE" },
  gate: { label: "CI Gate", render: pageGate, group: "WORKSPACE" },
  reports: { label: "Reports", render: pageReports, group: "WORKSPACE" },
  test_drive: { label: "Test Drive", render: pageTestDrive, group: "WORKSPACE" },
  rules: { label: "Rules", render: pageRules, group: "WORKSPACE" },
  trust: { label: "Trust", render: pageTrust, group: "WORKSPACE" },
  documentation: { label: "Documentation", render: pageDocumentation, group: "WORKSPACE" },
  // RESULTS — analysis-result views, shown once an analysis exists.
  overview: { label: "Summary", render: pageOverview, group: "RESULTS" },
  supply: { label: "Supply Network", render: pageSupply, group: "RESULTS" },
  pst: { label: "Power States", render: pagePST, group: "RESULTS" },
  strategies: { label: "Strategies", render: pageStrategies, group: "RESULTS" },
  design: { label: "Design", render: pageDesign, group: "RESULTS" },
  coverage: { label: "Coverage", render: pageCoverage, group: "RESULTS" },
  readiness: { label: "Health", render: pageReadiness, group: "RESULTS" },
  support: { label: "Support", render: pageSupport, group: "RESULTS" },
  export: { label: "Export", render: pageExport, group: "RESULTS" },
};

const GROUP_ORDER = ["WORKSPACE", "RESULTS"];

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
    if (group === "RESULTS" && !App.state.analysis) return "";
    const label = group === "RESULTS" && !App.state.analysis ? "" : group;
    return `<div class="nav-group"><span class="nav-group-label">${label}</span>${items.map(([id, l]) => navItemHtml(id, l, current)).join("")}</div>`;
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
