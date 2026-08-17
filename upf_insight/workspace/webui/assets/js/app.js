/* ═══════════════════════════════════════════════════════════════════════════
   UPF-Insight - app.js
   Shell bootstrap · hash router · nav · top-bar context · status rail ·
   page event wiring · background canvas init. Mirrors the Ṛta app.js shell.
   ═══════════════════════════════════════════════════════════════════════════ */

import { esc, escAttr, statusBadge, setStatusMeta, setTokens } from "./theme.js";
import { emptyState, sourceViewer, sectionTitle, metricRow, table } from "./components.js";
import { initBackground } from "./viz.js";
import {
  App, PAGES, navGroupsHtml, toast, openInspector, closeInspector,
  findingObj, findingLoc, locLines, genEmptyRowHtml, genFieldKeys,
  fetchSample,
} from "./pages.js";

// The pre-loaded sample: a realistic 3-domain UPF with always-on logic,
// isolation and retention (the golden example from the test suite).
const SAMPLE = `# example.soc.upf - small golden example for UPF-Insight validation.
# A typical 3-domain SoC with always-on logic, isolation, and retention.
upf_version 3.0
set_design_top soc_top

# ---- Supply network ----
create_supply_port vdd -direction in
create_supply_port vss -direction in
create_supply_net vdd -resolve port
create_supply_net vss -resolve port
connect_supply_net vdd -ports vdd
connect_supply_net vss -ports vss

create_supply_set primary -function {power vdd} -function {ground vss}
create_supply_set vdd_ret -function {power {net vdd_ret_net}} -function {ground vss}

# ---- Power domains ----
create_power_domain PD_CORE -elements {u_cpu} -primary_supply_set primary
create_power_domain PD_IO   -elements {u_io}   -primary_supply_set primary
create_power_domain PD_SRAM -elements {u_sram} -primary_supply_set vdd_ret

# ---- Power states ----
add_port_state vdd -state {ON 1.0} -state {OFF 0.0}
add_port_state vss -state {ON 0.0}
create_pst pst_soc -supplies {vdd vss}
add_pst_state PS_ON  -pst pst_soc -state {vdd ON vss ON}
add_pst_state PS_OFF -pst pst_soc -state {vdd OFF vss ON}
add_state_transition PS_ON -next_state PS_OFF
add_state_transition PS_OFF -next_state PS_ON

# ---- Strategies ----
set_isolation iso_core_to_io -domain PD_CORE -isolation_supply primary \\
    -clamp_value 0 -applies_to outputs -isolation_signal iso_en
set_retention ret_sram -domain PD_SRAM -retention_supply vdd_ret \\
    -save_signal save -restore_signal restore
`;

const SAMPLE_DESIGN = `{
  "instances": {
    "u_cpu":  {"module": "cpu_core",  "sequential": true},
    "u_io":   {"module": "io_block",  "sequential": false},
    "u_sram": {"module": "sram_1rw",  "sequential": true}
  },
  "ports": ["clk", "reset_n", "iso_en", "save", "restore"],
  "signals": {
    "req_a": {"driver": "u_cpu", "receivers": ["u_io"]}
  },
  "pg_pins": {
    "cpu_core": ["VDD", "VSS"],
    "io_block": ["VDD_IO", "VSS"],
    "sram_1rw": ["VDD_RET", "VSS"]
  }
}`;

let current = "overview";
let rulesCache = null;

const $ = (sel) => document.querySelector(sel);

async function boot() {
  initBackground($("#bg"));
  try {
    const design = await fetch("/api/design").then(r => r.json());
    setStatusMeta(design);
    setTokens(design);
    if (design.version) $("#ver").textContent = `v${design.version}`;
  } catch (e) { /* fallback metadata used */ }
  try {
    rulesCache = (await fetch("/api/rules").then(r => r.json())).rules || [];
    App.state.rules = rulesCache;
  } catch (e) { App.state.rules = []; }

  if (!App.state.upf) {
    App.state.upf = SAMPLE;
    App.state.filename = "example.soc.upf";
  }

  window.addEventListener("hashchange", route);
  $("#inspector-close").addEventListener("click", closeInspector);
  $("#inspector-backdrop").addEventListener("click", closeInspector);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeInspector(); closeMenus(); closePalette(); }
    const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if ((e.key === "/" || (e.key === "k" && (e.ctrlKey || e.metaKey))) && !inField) {
      e.preventDefault();
      openPalette();
    }
  });

  wireCommandBar();
  wirePalette();
  const brand = $(".cmdbar-brand");
  if (brand) brand.addEventListener("click", () => { location.hash = "#/home"; });
  const homeBtn = $("#cmd-home");
  if (homeBtn) homeBtn.addEventListener("click", () => { location.hash = "#/home"; });

  route();
}

function closeMenus() {
  // Command menus were removed from the top bar (Phase E cleanup); this
  // remains a no-op hook so callers keep working.
}

/* ── Command palette (Ctrl/Cmd+K or /) - real actions only ─────────────── */
const PALETTE_COMMANDS = [
  { icon: "◈", label: "Validate current UPF", hint: "validator", go: "validator" },
  { icon: "❐", label: "Generate UPF", hint: "generator", go: "generator" },
  { icon: "⇄", label: "Compare UPF (Diff)", hint: "diff", go: "diff" },
  { icon: "⌦", label: "Run CI Gate", hint: "gate", go: "gate" },
  { icon: "⇩", label: "Export JSON", hint: "export", go: "export" },
  { icon: "❐", label: "Generate Report", hint: "reports", go: "reports" },
  { icon: "▶", label: "Test Drive", hint: "test_drive", go: "test_drive" },
  { icon: "◫", label: "Open Power States", hint: "pst", go: "pst" },
  { icon: "▤", label: "Open Supply Network", hint: "supply", go: "supply" },
  { icon: "⇄", label: "Open Strategies", hint: "strategies", go: "strategies" },
  { icon: "◉", label: "Open Domain Relations", hint: "relations", go: "relations" },
  { icon: "▦", label: "Open Coverage", hint: "coverage", go: "coverage" },
  { icon: "◫", label: "Open Health (Readiness)", hint: "readiness", go: "readiness" },
  { icon: "☰", label: "Rules Registry", hint: "rules", go: "rules" },
  { icon: "◆", label: "Trust Model", hint: "trust", go: "trust" },
  { icon: "❐", label: "Documentation", hint: "documentation", go: "documentation" },
  { icon: "◈", label: "Home", hint: "home", go: "home" },
];

let paletteActive = -1;
function openPalette() {
  const box = $("#palette");
  if (!box) return;
  box.hidden = false;
  box.setAttribute("aria-hidden", "false");
  paletteActive = -1;
  const input = $("#palette-input");
  if (input) { input.value = ""; input.focus(); }
  renderPalette("");
}
function closePalette() {
  const box = $("#palette");
  if (!box || box.hidden) return;
  box.hidden = true;
  box.setAttribute("aria-hidden", "true");
  paletteActive = -1;
}
function renderPalette(q) {
  const list = $("#palette-list");
  if (!list) return;
  const ql = q.trim().toLowerCase();
  const items = ql
    ? PALETTE_COMMANDS.filter(c => (c.label + " " + c.hint).toLowerCase().includes(ql))
    : PALETTE_COMMANDS;
  paletteActive = items.length ? 0 : -1;
  list.innerHTML = items.length
    ? items.map((c, i) =>
        `<button class="palette-item${i === paletteActive ? " active" : ""}" data-palette-i="${i}" role="option" aria-selected="${i === paletteActive}" type="button">
           <span class="pi-icon">${c.icon}</span><span>${esc(c.label)}</span><span class="pi-hint">${esc(c.hint)}</span>
         </button>`).join("")
    : `<div class="palette-empty">no matching commands</div>`;
  list.querySelectorAll("[data-palette-i]").forEach(b => b.addEventListener("click", () => {
    const i = +b.dataset.paletteI;
    const c = items[i];
    if (c) { closePalette(); location.hash = `#/${c.go}`; }
  }));
}
function wirePalette() {
  const input = $("#palette-input");
  const list = $("#palette-list");
  const box = $("#palette");
  if (!input || !list || !box) return;
  input.addEventListener("input", () => renderPalette(input.value));
  input.addEventListener("keydown", (e) => {
    const items = list.querySelectorAll("[data-palette-i]");
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!items.length) return;
      paletteActive = (paletteActive + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items.forEach((b, i) => { b.classList.toggle("active", i === paletteActive); b.setAttribute("aria-selected", String(i === paletteActive)); });
      items[paletteActive].scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (items[paletteActive]) items[paletteActive].click();
    } else if (e.key === "Escape") {
      closePalette();
    }
  });
  box.addEventListener("click", (e) => { if (e.target === box) closePalette(); });
}

function currentView() {
  const h = location.hash.replace(/^#\/?/, "");
  if (PAGES[h]) return h;
  return App.state.analysis ? "validator" : "home";
}

async function route() {
  const view = currentView();
  current = view;
  document.body.classList.toggle("no-analysis", !App.state.analysis);
  renderNav();
  const main = $("#main");
  main.innerHTML = "";
  const page = PAGES[view];
  if (!page) { main.innerHTML = emptyState("Unknown page", "That workspace page does not exist."); return; }
  try {
    const html = await page.render();
    main.innerHTML = html;
    wirePage(view);
    updateContext();
  } catch (e) {
    main.innerHTML = `
      <div class="page">
        <p class="page-eyebrow">ERROR</p>
        <h1 class="page-title">Page failed to render</h1>
        <div class="err err-engine"><span class="e-kind">Engine failure</span><span class="err-msg">${esc(e.message || String(e))}</span></div>
      </div>`;
  }
}

function renderNav() {
  $("#nav-groups").innerHTML = navGroupsHtml(current);
  $("#nav-groups").querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.view) location.hash = `#/${btn.dataset.view}`;
    });
  });
}

function currentSessionName() {
  const s = App.state.session;
  return s && s.name ? s.name : "Untitled session";
}

function newSession() {
  App.state.session = { id: null, name: "Untitled session", status: "EMPTY", createdAt: null,
                        upf: SAMPLE, netlist: "", filename: "example.soc.upf", analysis: null };
  App.state.analysis = null;
  App.state.upf = SAMPLE;
  App.state.filename = "example.soc.upf";
  App.state.filters = { sev: "All", rule: "All", q: "" };
  App.state.ruleFilter = "All";
  toast("New session started - sample UPF loaded");
  if (location.hash !== "#/new_analysis") location.hash = "#/new_analysis";
  route();
}

function pushRecentSession() {
  const s = App.state.session;
  if (!s || !s.id) return;
  const prev = App.state.recentSessions.find(x => x.id === s.id);
  const entry = { id: s.id, name: s.name, createdAt: s.createdAt, status: s.status,
                  readiness: (s.analysis || {}).readiness ? (s.analysis.readiness.overall || "") : "" };
  if (prev) Object.assign(prev, entry);
  else { App.state.recentSessions.unshift(entry); App.state.recentSessions = App.state.recentSessions.slice(0, 8); }
}

function adoptAnalysis(res, opts = {}) {
  const prev = App.state.session || {};
  const file = opts.filename || App.state.filename || "pasted.upf";
  const fileChanged = !!(opts.filename) && opts.filename !== (prev.filename || "");
  const id = prev.id && !fileChanged ? prev.id : `sess-${Date.now()}`;
  App.state.session = {
    id,
    name: opts.name || file.replace(/\.[^.]+$/, ""),
    status: "ANALYZED",
    createdAt: prev.createdAt && !fileChanged ? prev.createdAt : new Date().toISOString(),
    upf: opts.upf || "", netlist: opts.netlist || "",
    filename: file,
    analysis: res,
  };
  if (opts.filename) App.state.filename = opts.filename;
  pushRecentSession();
}

function restoreSession(entry) {
  const s = App.state.session;
  if (!s || s.id !== entry.id) {
    toast("Session context is in-memory for this tab - re-run the analysis to restore evidence.", true);
    return;
  }
  location.hash = "#/overview";
  updateContext();
}

function showRecentSessions() {
  const list = App.state.recentSessions;
  if (!list.length) {
    openInspector("Recent Sessions",
      `<div class="insp-section"><div class="insp-v">No sessions yet in this browser tab.</div></div>
       <div class="insp-section"><div class="insp-k">Note</div><div class="insp-v">Sessions are held in memory for the current tab; re-analyzing restores full evidence.</div></div>`);
    return;
  }
  const cur = App.state.session ? App.state.session.id : null;
  const html = list.map((e, i) => `
    <button class="insp-row" data-sess="${i}" type="button">
      <span class="insp-k">${esc(e.name)}</span>
      <span class="insp-v mono">${esc(new Date(e.createdAt).toLocaleTimeString())} · ${esc(e.status)}${e.readiness ? " · " + esc(e.readiness) : ""}${e.id !== cur ? " · re-run to restore" : ""}</span>
    </button>`).join("");
  openInspector("Recent Sessions", html);
  document.querySelectorAll("#inspector-body [data-sess]").forEach(btn => {
    btn.addEventListener("click", () => restoreSession(list[+btn.dataset.sess]));
  });
}

function wireCommandBar() {
  const search = $("#cmd-search");
  if (search) {
    const apply = () => {
      const q = search.value.trim().toLowerCase();
      let visible = 0;
      document.querySelectorAll("#nav-groups .nav-group").forEach(g => {
        let gv = 0;
        g.querySelectorAll(".nav-item").forEach(it => {
          const hit = !q || it.textContent.toLowerCase().includes(q);
          it.hidden = !hit;
          if (hit) gv++;
        });
        g.hidden = gv === 0;
        visible += gv;
      });
      const empty = $("#nav-empty");
      if (empty) empty.hidden = visible !== 0;
    };
    search.addEventListener("input", apply);
    search.addEventListener("keydown", e => { if (e.key === "Escape") { search.value = ""; apply(); search.blur(); } });
  }

}

function updateContext() {
  const a = App.state.analysis;
  const sess = App.state.session;
  const ctx = {
    file: a ? App.state.filename : (sess.filename || "-"),
    mode: a ? (a.readiness || {}).mode || "UPF_ONLY" : "-",
    design: (a && a.model && a.model.design) ? "design: loaded" : (sess.netlist ? "design: loaded" : "no design"),
  };
  const fEl = document.querySelector('[data-ctx="file"]');
  if (fEl) fEl.textContent = ctx.file;
  const mEl = document.querySelector('[data-ctx="mode"]');
  if (mEl) mEl.textContent = ctx.mode;
  const dEl = document.querySelector('[data-ctx="design"]');
  if (dEl) dEl.textContent = ctx.design;
  const nameEl = $("#session-name");
  if (nameEl) nameEl.textContent = currentSessionName();
  const timeEl = $("#session-time");
  if (timeEl) timeEl.textContent = sess.createdAt ? new Date(sess.createdAt).toLocaleTimeString() : "";
  const scopeEl = $("#session-scope");
  const statEl = $("#session-status");
  const trustEl = $("#ctx-trust"), rdyEl = $("#ctx-readiness");
  if (a) {
    const c = a.check || {};
    const counts = c.counts || {};
    if (scopeEl) scopeEl.textContent = `${counts.errors ?? 0}E · ${counts.warnings ?? 0}W · ${a.command_count ?? 0} cmd`;
    if (statEl) statEl.textContent = sess.status || "ANALYZED";
    trustEl.innerHTML = statusBadge("trust", (a.support ? trustOf(a.support) : "NOT_VALIDATED"));
    rdyEl.innerHTML = statusBadge("readiness", (a.readiness || {}).overall || "-");
  } else {
    if (scopeEl) scopeEl.textContent = "";
    if (statEl) statEl.textContent = sess.status || "EMPTY";
    trustEl.innerHTML = ""; rdyEl.innerHTML = "";
  }
  syncSessionHeadVisibility();
  const rail = $("#rail");
  if (!a) {
    rail.innerHTML = `<span class="rail-item"><span class="rail-label">status</span><span>no analysis loaded</span></span>
      <span class="rail-item"><span class="rail-label">engine</span><span class="mono">deterministic · offline</span></span>`;
    return;
  }
  const c = a.check || {};
  const counts = c.counts || {};
  rail.innerHTML = `
    <span class="rail-item"><span class="rail-label">errors</span><span class="rail-num" style="color:${counts.errors ? "var(--error)" : "var(--success)"}">${counts.errors ?? 0}</span></span>
    <span class="rail-item"><span class="rail-label">warnings</span><span class="rail-num" style="color:${counts.warnings ? "var(--warning)" : "var(--text-primary)"}">${counts.warnings ?? 0}</span></span>
    <span class="rail-item"><span class="rail-label">info</span><span class="rail-num">${counts.infos ?? 0}</span></span>
    <span class="rail-item"><span class="rail-label">commands</span><span class="rail-num">${a.command_count ?? 0}</span></span>
    <span class="rail-item"><span class="rail-label">mode</span><span class="mono" style="color:var(--text-secondary)">${esc((a.readiness || {}).mode || "UPF_ONLY")}</span></span>
  `;
}

// Hide status-strip items (and their separators) that have no real value yet.
// The strip is a status readout, not a set of buttons.
function syncSessionHeadVisibility() {
  const head = document.getElementById("session-head");
  if (!head) return;
  let prevSep = null;
  for (const child of head.children) {
    if (child.classList.contains("sh-sep")) { prevSep = child; continue; }
    const t = (child.textContent || "").trim();
    const empty = t === "" || t === "-";
    child.hidden = empty;
    if (prevSep) prevSep.hidden = empty;
    prevSep = null;
  }
}

function trustOf(support) {
  if (!support || !support.statuses) return "NOT_VALIDATED";
  const s = support.statuses;
  if (s.NETLIST_REQUIRED) return "NETLIST_REQUIRED";
  if (s.TCL_EXECUTION_REQUIRED) return "TCL_EXECUTION_REQUIRED";
  if (s.UNSUPPORTED) return "UNSUPPORTED";
  if (s.PARTIALLY_VALIDATED) return "PARTIALLY_VALIDATED";
  if (s.VALIDATED) return "VALIDATED";
  return "NOT_VALIDATED";
}

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE EVENT WIRING
   ═══════════════════════════════════════════════════════════════════════════ */

async function wirePage(view) {
  const main = $("#main");
  if (view === "new_analysis") wireNewAnalysis(main);
  else if (view === "validator") wireValidator(main);
  else if (view === "export") wireExport(main);
  else if (view === "rules") wireRules(main);
  else if (view === "test_drive") wireTestDrive(main);
  else if (view === "generator") wireGenerator(main);
  else if (view === "home") wireHome(main);
  else if (view === "diff") wireDiff(main);
  else if (view === "gate") wireGate(main);
  else if (view === "reports") wireReports(main);
  else if (view === "overview" || view === "supply" || view === "pst" || view === "strategies"
           || view === "relations" || view === "coverage" || view === "readiness"
           || view === "support" || view === "design") {
    wireStandalone(main, view);
    wireCrossLinks(main);
    wireRelations(main);
  }
}

/* Standalone feature input - every result page owns its UPF input + Analyze.
   Runs the same deterministic engine; lands back on the same page with results. */
function wireStandalone(main, view) {
  const upfEl = $("#sa-upf");
  if (!upfEl) return;
  upfEl.addEventListener("input", () => { App.state.upf = upfEl.value; });
  const pick = $("#sa-pick");
  if (pick) pick.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".upf,.tcl,.txt";
    inp.addEventListener("change", async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      const text = await f.text();
      App.state.upf = text; App.state.filename = f.name || "pasted.upf";
      upfEl.value = text;
      const fEl = $("#sa-file"); if (fEl) fEl.textContent = App.state.filename;
      toast(`Loaded ${App.state.filename}`);
    });
    inp.click();
  });
  const sample = $("#sa-sample");
  if (sample) sample.addEventListener("click", () => {
    App.state.upf = SAMPLE; App.state.filename = "example.soc.upf";
    upfEl.value = SAMPLE;
    const fEl = $("#sa-file"); if (fEl) fEl.textContent = App.state.filename;
    toast("Sample loaded - golden 3-domain SoC UPF");
  });
  const clear = $("#sa-clear");
  if (clear) clear.addEventListener("click", () => {
    App.state.upf = ""; App.state.filename = "pasted.upf";
    upfEl.value = "";
    const fEl = $("#sa-file"); if (fEl) fEl.textContent = "pasted.upf";
  });
  const run = $("#sa-analyze");
  if (run) run.addEventListener("click", async () => {
    const upf = upfEl.value.trim();
    if (!upf) { toast("Load or paste a UPF file first", true); return; }
    App.state.upf = upf;
    await runAnalyze({ content: upf, file: App.state.filename }, view);
  });
}

/* Domain Relations page: matrix cells + evidence buttons open the relation
   detail panel (provenance from the engine, nothing invented). */
function wireRelations(main) {
  const cells = main.querySelectorAll("[data-rel-cell]");
  cells.forEach(c => c.addEventListener("click", () => {
    const [f, t] = (c.dataset.relCell || "").split("|");
    if (!f || !t || f === t) return;
    const rel = (App.state.analysis || {}).relations || {};
    const found = (rel.relations || []).find(r => r.from_domain === f && r.to_domain === t);
    const aon = (rel.domains || []).filter(d => d.type === "ALWAYS_ON").map(d => d.name);
    const sw = (rel.domains || []).filter(d => d.type === "SWITCHABLE").map(d => d.name);
    const lines = [
      `<div class="insp-section"><div class="insp-k">Relationship</div><div class="insp-v mono">${esc(f)} → ${esc(t)}</div></div>`,
      `<div class="insp-section"><div class="insp-k">Label</div><div class="insp-v mono">${esc((c.textContent || "").trim() || "-")}</div></div>`,
    ];
    if (found && found.kinds && found.kinds.length) {
      lines.push(`<div class="insp-section"><div class="insp-k">Kinds</div><div class="insp-v mono">${esc(found.kinds.join(", "))}</div></div>`);
      const evs = (found.evidence || []).map(e => {
        const loc = e.line ? ` <span style="color:var(--text-muted)">L${esc(String(e.line))}${e.file ? " in " + esc(e.file) : ""}</span>` : "";
        return `<div class="ilink"><span class="il-rule">${esc(e.kind)}</span><span class="il-a">${esc(e.detail)}</span>${loc ? `<span class="il-loc">${loc}</span>` : ""}</div>`;
      }).join("");
      lines.push(`<div class="insp-section"><div class="insp-k">Evidence</div>${evs}</div>`);
    } else {
      lines.push(`<div class="insp-section"><div class="insp-k">Evidence</div><div class="insp-v">No proven relationship - UNKNOWN is not a defect, the engine found no evidence for ${esc(f)} → ${esc(t)}.</div></div>`);
    }
    lines.push(`<div class="insp-section"><div class="insp-k">Context</div><div class="insp-v">Always-on: ${esc(aon.join(", ") || "none")} · Switchable: ${esc(sw.join(", ") || "none")}</div></div>`);
    openInspector(`${esc(f)} → ${esc(t)}`, lines.join(""));
  }));
  main.querySelectorAll("[data-rel-ev]").forEach(b => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const [f, t] = (b.dataset.relEv || "").split("|");
    const cell = main.querySelector(`[data-rel-cell="${CSS.escape(f)}|${CSS.escape(t)}"]`);
    if (cell) cell.click();
  }));
}

function wireNewAnalysis(main) {
  const upfEl = $("#na-upf");
  const netEl = $("#na-netlist");
  if (upfEl) upfEl.addEventListener("input", () => { App.state.upf = upfEl.value; });
  const readFile = (inp, cb) => inp.addEventListener("change", async () => {
    const f = inp.files && inp.files[0];
    if (f) cb(await f.text(), f.name);
  });
  const upfPick = document.createElement("input");
  upfPick.type = "file"; upfPick.accept = ".upf,.tcl,.txt";
  readFile(upfPick, (text, name) => {
    App.state.upf = text; App.state.filename = name;
    upfEl.value = text; const fEl = $("#na-file"); if (fEl) fEl.textContent = name;
    toast(`Loaded ${name}`);
  });
  const p1 = $("#na-pick"); if (p1) p1.addEventListener("click", () => upfPick.click());
  const netPick = document.createElement("input");
  netPick.type = "file"; netPick.accept = ".json,.txt";
  readFile(netPick, (text, name) => {
    netEl.value = text; const nEl = $("#na-net-file"); if (nEl) nEl.textContent = name;
    toast(`Design context ${name} loaded`);
  });
  const p2 = $("#na-net-pick"); if (p2) p2.addEventListener("click", () => netPick.click());
  const samp = $("#na-sample");
  if (samp) samp.addEventListener("click", () => {
    App.state.upf = SAMPLE; App.state.filename = "example.soc.upf";
    upfEl.value = SAMPLE;
    const fEl = $("#na-file"); if (fEl) fEl.textContent = "example.soc.upf";
    netEl.value = SAMPLE_DESIGN;
    const nEl = $("#na-net-file"); if (nEl) nEl.textContent = "example.design.json";
    toast("Sample loaded - golden 3-domain SoC UPF");
  });
  const clear = $("#na-clear");
  if (clear) clear.addEventListener("click", () => {
    App.state.upf = ""; upfEl.value = ""; App.state.filename = "pasted.upf";
    const fEl = $("#na-file"); if (fEl) fEl.textContent = "pasted.upf";
  });
  const nclear = $("#na-net-clear");
  if (nclear) nclear.addEventListener("click", () => {
    netEl.value = ""; const nEl = $("#na-net-file"); if (nEl) nEl.textContent = "no design context";
  });
  const run = $("#na-analyze");
  if (run) run.addEventListener("click", async () => {
    const upf = upfEl.value.trim();
    if (!upf) { toast("Load or paste a UPF file first", true); return; }
    App.state.upf = upf;
    await runAnalyze({
      content: upf, file: App.state.filename,
      design: netEl.value.trim() ? parseDesign(netEl.value) : undefined,
    }, "validator");
  });
}

function parseDesign(text) {
  try { return JSON.parse(text); }
  catch (e) { toast("Design context is not valid JSON - run without it", true); return undefined; }
}

function wireValidator(main) {
  const upfEl = $("#val-upf");
  const netEl = $("#val-netlist");
  if (upfEl) upfEl.addEventListener("input", () => App.state.upf = upfEl.value);

  const vpick = $("#val-pick");
  if (vpick) vpick.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".upf,.tcl,.txt";
    inp.addEventListener("change", async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      const text = await f.text();
      App.state.upf = text; App.state.filename = f.name || "pasted.upf";
      if (upfEl) upfEl.value = text;
      const vf = $("#val-file"); if (vf) vf.textContent = App.state.filename;
      toast(`Loaded ${App.state.filename}`);
    });
    inp.click();
  });

  const vls = $("#val-load-sample");
  if (vls) vls.addEventListener("click", () => {
    App.state.upf = SAMPLE;
    App.state.filename = "example.soc.upf";
    if (upfEl) upfEl.value = SAMPLE;
    const vf = $("#val-file"); if (vf) vf.textContent = App.state.filename;
    if (netEl) netEl.value = SAMPLE_DESIGN;
  });
  const vcl = $("#val-clear");
  if (vcl) vcl.addEventListener("click", () => {
    App.state.upf = ""; if (upfEl) upfEl.value = ""; App.state.filename = "pasted.upf";
    const vf = $("#val-file"); if (vf) vf.textContent = App.state.filename;
    if (netEl) netEl.value = "";
  });
  const van = $("#val-analyze");
  if (van) van.addEventListener("click", async () => {
    const upf = upfEl ? upfEl.value.trim() : "";
    if (!upf) { toast("Paste or upload a UPF file first", true); return; }
    App.state.upf = upf;
    App.state.filename = App.state.filename || "pasted.upf";
    await runAnalyze({ content: upf, file: App.state.filename, design: netEl && netEl.value.trim() ? parseDesign(netEl.value) : undefined });
  });

  const fq = $("#f-q");
  if (fq) fq.addEventListener("input", () => { App.state.filters.q = fq.value; route(); });
  main.querySelectorAll("#f-rule").forEach(sel => {
    sel.addEventListener("change", () => { App.state.filters.rule = sel.value; route(); });
  });
  main.querySelectorAll("[data-seg]").forEach(btn => {
    btn.addEventListener("click", () => { App.state.filters.sev = btn.dataset.seg; route(); });
  });
  const fc = $("#f-clear");
  if (fc) fc.addEventListener("click", () => {
    App.state.filters = { sev: "All", rule: "All", q: "" }; route();
  });

  main.querySelectorAll(".tbl tbody tr.row-click").forEach(tr => {
    tr.addEventListener("click", () => {
      const i = +tr.dataset.idx;
      const a = App.state.analysis;
      if (!a) return;
      const it = ((a.check || {}).findings || [])[i];
      if (!it) return;
      const rule = rulesCache ? rulesCache.find(r => r.code === it.rule) : null;
      openInspector(`${it.rule} - Finding`, findingDetail(it, rule));
    });
  });
}

const STAGES = ["preprocess", "build", "check", "support", "pst", "readiness", "coverage", "result"];

async function runAnalyze(payload, after = null) {
  const main = $("#main");
  main.innerHTML = `
    <div class="page">
      <p class="page-eyebrow">ANALYZE</p>
      <h1 class="page-title">Analyzing power intent</h1>
      <div class="analyzing"><div class="spinner" aria-hidden="true"></div>
        <div class="stage-track">
          ${STAGES.map((s, i) => `<span class="stage${i === 0 ? " active" : ""}">${s}</span>`).join("")}
        </div>
        <span class="mono" style="font-size:11.5px;color:var(--text-muted)">running the deterministic pipeline locally…</span>
      </div>
    </div>`;
  const track = main.querySelector(".stage-track");
  const advance = (idx) => {
    const stages = track.querySelectorAll(".stage");
    stages.forEach((s, i) => {
      s.classList.toggle("done", i < idx);
      s.classList.toggle("active", i === idx);
    });
  };
  try {
    const res = await post("/api/validate", payload);
    advance(STAGES.length);
    App.state.analysis = res;
    adoptAnalysis(res, { upf: payload.content, netlist: payload.design ? "loaded" : "",
                         filename: payload.file || App.state.filename });
    await new Promise(r => setTimeout(r, 350));
    if (after) {
      // Setting the same hash is a no-op (no hashchange event), so re-render
      // explicitly when the target view is already the current one.
      if (location.hash === `#/${after}`) {
        route();
      } else {
        location.hash = `#/${after}`;
      }
    } else {
      route();
    }
  } catch (e) {
    main.innerHTML = `
      <div class="page">
        <p class="page-eyebrow">ANALYZE</p>
        <h1 class="page-title">Validate</h1>
        <div class="err err-engine"><span class="e-kind">Engine failure</span><span class="err-msg">${esc(e.message || String(e))}</span></div>
      </div>`;
    toast("Analysis failed", true);
  }
}

import { findingDetailHtml } from "./components.js";
function findingDetail(it, rule) {
  return findingDetailHtml({
    sev: it.severity, code: it.rule, msg: it.message, obj: it.file || "", loc: findingLoc(it),
    line: it.line, line2: null,
  }, rule);
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) { let d = `HTTP ${r.status}`; try { const j = await r.json(); d = j.detail || j.error || d; } catch (e) {} throw new Error(d); }
  return r.json();
}

/* ── Export ─────────────────────────────────────────────────────────────── */
function wireExport(main) {
  const dl = (name, content, mime) => {
    const b = new Blob([content], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = name; a.click();
    URL.revokeObjectURL(a.href);
    toast(`Downloaded ${name}`);
  };
  const jb = $("#exp-json");
  if (jb) jb.addEventListener("click", () => {
    dl("analysis_result.json", JSON.stringify(App.state.analysis, null, 2), "application/json");
  });
  const rdy = $("#exp-rdy");
  if (rdy) rdy.addEventListener("click", () => {
    const r = (App.state.analysis || {}).readiness || {};
    dl("readiness_evidence.json", JSON.stringify(r, null, 2), "application/json");
  });
}

/* ── Rules ──────────────────────────────────────────────────────────────── */
function wireRules(main) {
  main.querySelectorAll("[data-seg]").forEach(btn => {
    btn.addEventListener("click", () => { App.state.ruleFilter = btn.dataset.seg; route(); });
  });
  const gen = $("#rules-gen");
  if (gen) gen.addEventListener("click", () => { location.hash = "#/generator"; });
  const q = $("#rule-q");
  if (q) q.addEventListener("input", () => { App.state.ruleQ = q.value; route(); });
  const layerSel = $("#rule-layer");
  if (layerSel) layerSel.addEventListener("change", () => { App.state.ruleLayer = layerSel.value; route(); });
  const dlJson = $("#rules-dl-json");
  if (dlJson) dlJson.addEventListener("click", () => {
    const rules = App.state.rules || [];
    const blob = new Blob([JSON.stringify({ rules }, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "upf_rules.json"; a.click();
    URL.revokeObjectURL(a.href); toast("Downloaded upf_rules.json");
  });
  const dlMd = $("#rules-dl-md");
  if (dlMd) dlMd.addEventListener("click", () => {
    const rules = App.state.rules || [];
    const lines = ["# UPF-Insight Rules Reference", "", `Total: ${rules.length} rules`, ""];
    rules.forEach(r => lines.push(`## ${r.code} - ${r.title}`, "", `- **Severity:** ${r.severity}`, `- **Layer:** ${r.layer}`, `- **Description:** ${r.description}`, ""));
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "upf_rules.md"; a.click();
    URL.revokeObjectURL(a.href); toast("Downloaded upf_rules.md");
  });
}

/* ── Test Drive ─────────────────────────────────────────────────────────── */
const TD_SAMPLES = {
  good: "upf_version 3.0\nset_design_top top\ncreate_supply_port vdd -direction in\ncreate_supply_net vdd -resolve port\ncreate_supply_set primary -function {power vdd}\ncreate_power_domain PD -elements {u0} -primary_supply_set primary\nadd_port_state vdd -state {ON 1.0} -state {OFF 0.0}\ncreate_pst pst -supplies {vdd}\nadd_pst_state RUN -pst pst -state {vdd ON}\nadd_pst_state OFF -pst pst -state {vdd OFF}\n",
  bad: "create_power_domain PD -elements {u0} -primary_supply_set missing\nset_isolation iso -domain NOPE -isolation_supply missing -clamp_value 0\nadd_pst_state RUN -pst missing -state {vdd ON}\n",
  design: "create_supply_port vdd -direction in\ncreate_supply_net vdd -resolve port\ncreate_supply_set primary -function {power vdd}\ncreate_power_domain PD -elements {u_cpu} -primary_supply_set primary\nadd_port_state vdd -state {ON 1.0}\ncreate_pst pst -supplies {vdd}\nadd_pst_state RUN -pst pst -state {vdd ON}\nset_retention ret -domain PD -retention_supply vdd -save_signal save -restore_signal restore\n",
};
function wireTestDrive(main) {
  const tr = $("#td-run");
  const tdl = $("#td-dl");
  if (!tr) return;
  const enableDl = () => { if (tdl) tdl.disabled = !App.state.analysis; };
  if (tdl) tdl.addEventListener("click", () => {
    if (!App.state.analysis) { toast("Run a scenario first", true); return; }
    const blob = new Blob([JSON.stringify(App.state.analysis, null, 2)], { type: "application/json" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "test_drive_result.json"; a.click();
    URL.revokeObjectURL(a.href); toast("Downloaded test_drive_result.json");
  });
  tr.addEventListener("click", async () => {
    const which = $("#td-sample").value;
    if (which === "regression") { await runRegression(); enableDl(); return; }
    const upf = TD_SAMPLES[which] || "";
    const design = which === "design" ? JSON.parse(SAMPLE_DESIGN) : undefined;
    try {
      const res = await post("/api/validate", { content: upf, file: `sample_${which}.upf`, design });
      App.state.upf = upf;
      App.state.filename = `sample_${which}.upf`;
      App.state.analysis = res;
      adoptAnalysis(res, { upf, netlist: design ? "loaded" : "", filename: App.state.filename, name: `sample_${which}` });
      App.state.filters = { sev: "All", rule: "All", q: "" };
      enableDl();
      location.hash = "#/validator";
    } catch (e) { toast("Analysis failed", true); }
  });
}

/* Full-workflow Test Drive scenario: validate V2, diff V1→V2, gate V2 under
   STRICT - all against the real backend, then hand off to the real pages. */
async function runRegression() {
  const out = $("#td-out");
  out.innerHTML = `<div class="analyzing"><div class="spinner" aria-hidden="true"></div><span class="mono" style="font-size:12px;color:var(--text-muted)">running the full workflow - validate → diff → gate…</span></div>`;
  try {
    const v1 = await fetchSample("cpu_v1");
    const v2 = await fetchSample("cpu_v2");
    let design;
    try { design = JSON.parse(await fetchSample("cpu_design")); } catch (e) { design = undefined; }
    const res = await post("/api/validate", { content: v2, file: "cpu_subsys_v2.upf", design });
    App.state.upf = v2;
    App.state.filename = "cpu_subsys_v2.upf";
    App.state.analysis = res;
    adoptAnalysis(res, { upf: v2, netlist: design ? "loaded" : "", filename: App.state.filename, name: "cpu regression" });
    App.state.filters = { sev: "All", rule: "All", q: "" };
    App.state.diffA = v1; App.state.diffB = v2;
    App.state.diffFileA = "cpu_subsys_v1.upf"; App.state.diffFileB = "cpu_subsys_v2.upf";
    App.state.gateUpf = v2;
    App.state.reportUpf = v2;

    const [diffRes, gateRes] = await Promise.all([
      post("/api/diff", { old: v1, new: v2, old_file: "cpu_subsys_v1.upf", new_file: "cpu_subsys_v2.upf" }),
      post("/api/gate", { content: v2, policy: "STRICT", file: "cpu_subsys_v2.upf" }),
    ]);

    const counts = ((res.check || {}).counts) || {};
    const rdy = (res.readiness || {}).overall || "-";
    const gate = gateRes.gate || {};
    let h = sectionTitle("Regression workflow result", "V2 validated · diffed vs V1 · gated under STRICT");
    h += metricRow([
      { label: "Errors", value: counts.errors ?? 0 },
      { label: "Warnings", value: counts.warnings ?? 0 },
      { label: "Readiness", value: rdy },
      { label: "Semantic changes V1→V2", value: (diffRes.changes || []).length },
    ]);
    h += `<div class="ilink"><span class="il-rule">V2</span><span class="il-kind" style="color:var(--accent-2)">ANALYZED</span><span class="il-a">Validation of the candidate completed - open Findings for rule-level detail.</span><span class="il-loc"><button class="btn btn-sm" data-td-next="findings" type="button">Open Findings →</button></span></div>`;
    h += `<div class="ilink"><span class="il-rule">DIFF</span><span class="il-kind" style="color:var(--accent-2)">${(diffRes.changes || []).length} CHANGE(S)</span><span class="il-a">Semantic comparison of V1 vs V2 - investigate what changed in the power intent.</span><span class="il-loc"><button class="btn btn-sm" data-td-next="diff" type="button">Open Diff →</button></span></div>`;
    h += `<div class="ilink"><span class="il-rule">GATE</span><span class="il-kind" style="color:${gate.passed ? "var(--success)" : "var(--error)"}">${gate.passed ? "PASS" : "FAIL"}</span><span class="il-a">STRICT policy on V2 - ${((gate.reasons || []).join("; ")) || "passed"}.</span><span class="il-loc"><button class="btn btn-sm" data-td-next="gate" type="button">Open CI Gate →</button></span></div>`;
    h += `<div class="ilink"><span class="il-rule">REPORT</span><span class="il-kind" style="color:var(--accent-2)">EVIDENCE</span><span class="il-a">Generate an HTML/JSON report from this analysis.</span><span class="il-loc"><button class="btn btn-sm" data-td-next="reports" type="button">Open Reports →</button></span></div>`;
    h += `<p class="callout co-warning"><span><strong>Test Drive teaches the workflow, not the answer</strong> - use Findings, Diff and the Gate to investigate what V2 changed. CI PASS ≠ power-intent signoff.</span></p>`;
    out.innerHTML = h;
    out.querySelectorAll("[data-td-next]").forEach(btn => {
      btn.addEventListener("click", () => {
        const n = btn.dataset.tdNext;
        if (n === "findings") location.hash = "#/validator";
        else if (n === "diff") location.hash = "#/diff";
        else if (n === "gate") location.hash = "#/gate";
        else if (n === "reports") location.hash = "#/reports";
      });
    });
  } catch (e) {
    out.innerHTML = `<div class="err err-engine"><span class="e-kind">Workflow failure</span><span class="err-msg">${esc(e.message || String(e))}</span></div>`;
    toast("Regression workflow failed", true);
  }
}

/* ── Cross-page links ───────────────────────────────────────────────────── */
function wireCrossLinks(main) { /* default hash nav works */ }

/* ── UPF Diff (semantic) ────────────────────────────────────────────────── */
const DIFF_KIND_BADGE = {
  ADD: `<span class="sdc-status sev-success"><span class="sh circ"></span>ADD</span>`,
  REMOVE: `<span class="sdc-status sev-error"><span class="sh circ"></span>REMOVE</span>`,
  MODIFY: `<span class="sdc-status sev-warning"><span class="sh tri"></span>MODIFY</span>`,
};

function renderDiffResult(d) {
  const changes = d.changes || [];
  let h = `<div class="mono" style="font-size:12px;color:var(--text-secondary);margin:10px 0">semantic model diff - ${changes.length} change(s)</div>`;
  const side = (label, s) => `${label}: ${s.errors ?? 0}E · ${s.warnings ?? 0}W · ${esc(s.readiness || "-")}`;
  h += metricRow([
    { label: "Version A", value: side("", d.old || {}) },
    { label: "Version B", value: side("", d.new || {}) },
  ]);
  if (!changes.length) {
    h += `<p class="callout co-success"><span><strong>No semantic changes</strong> - both versions model the same power intent.</span></p>`;
  } else {
    h += table([{ label: "Kind" }, { label: "What" }, { label: "Object" }, { label: "Detail" }],
      changes.map((c, i) => ({ key: `${c.kind}-${c.what}-${c.name}-${i}`, cells: [
        { html: DIFF_KIND_BADGE[c.kind] || esc(c.kind) },
        { html: `<span class="mono">${esc(c.what)}</span>` },
        { html: `<span class="mono">${esc(c.name)}</span>` },
        { html: `<span class="msg mono">${esc(c.detail || "")}</span>` },
      ] })));
    h += `<p class="callout co-warning"><span><strong>Semantic, not textual</strong> - line/comment edits that do not change the model produce no changes.</span></p>`;
  }
  h += sectionTitle("Next actions");
  h += `<div class="caps-grid" style="grid-template-columns:repeat(3,minmax(0,1fr))">
    <button class="btn" data-diff-next="validateA" type="button">Validate Version A →</button>
    <button class="btn" data-diff-next="validateB" type="button">Validate Version B →</button>
    <button class="btn" data-diff-next="gateB" type="button">Run CI Gate on Version B →</button>
  </div>`;
  return h;
}

function wireDiff(main) {
  const aEl = $("#df-a"), bEl = $("#df-b");
  const pick = (target, fileEl, stateKey, fileKey) => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".upf,.tcl,.txt";
    inp.addEventListener("change", async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      target.value = await f.text();
      App.state[stateKey] = target.value;
      App.state[fileKey] = f.name || "pasted.upf";
      if (fileEl) fileEl.textContent = App.state[fileKey];
    });
    inp.click();
  };
  const $a = $("#df-pick-a"); if ($a) $a.addEventListener("click", () => pick(aEl, $("#df-file-a"), "diffA", "diffFileA"));
  const $b = $("#df-pick-b"); if ($b) $b.addEventListener("click", () => pick(bEl, $("#df-file-b"), "diffB", "diffFileB"));
  const sa = $("#df-sample-a"); if (sa) sa.addEventListener("click", async () => {
    try { aEl.value = await fetchSample("cpu_v1"); App.state.diffA = aEl.value; App.state.diffFileA = "cpu_subsys_v1.upf"; $("#df-file-a").textContent = App.state.diffFileA; toast("Sample V1 loaded - known-good CPU subsystem"); }
    catch (e) { toast(e.message, true); }
  });
  const sb = $("#df-sample-b"); if (sb) sb.addEventListener("click", async () => {
    try { bEl.value = await fetchSample("cpu_v2"); App.state.diffB = bEl.value; App.state.diffFileB = "cpu_subsys_v2.upf"; $("#df-file-b").textContent = App.state.diffFileB; toast("Sample V2 loaded - regressed CPU subsystem"); }
    catch (e) { toast(e.message, true); }
  });
  if (aEl) aEl.addEventListener("input", () => App.state.diffA = aEl.value);
  if (bEl) bEl.addEventListener("input", () => App.state.diffB = bEl.value);
  const run = $("#df-run");
  if (run) run.addEventListener("click", async () => {
    const oldText = (aEl ? aEl.value : "").trim();
    const newText = (bEl ? bEl.value : "").trim();
    if (!oldText || !newText) { toast("Provide both Version A and Version B", true); return; }
    try {
      const d = await post("/api/diff", {
        old: oldText, new: newText,
        old_file: App.state.diffFileA, new_file: App.state.diffFileB,
      });
      const out = $("#df-out");
      if (out) out.innerHTML = renderDiffResult(d);
      main.querySelectorAll("[data-diff-next]").forEach(btn => btn.addEventListener("click", () => {
        const n = btn.dataset.diffNext;
        if (n === "validateA") { App.state.upf = oldText; App.state.filename = App.state.diffFileA; location.hash = "#/validator"; }
        else if (n === "validateB") { App.state.upf = newText; App.state.filename = App.state.diffFileB; location.hash = "#/validator"; }
        else if (n === "gateB") { App.state.gateUpf = newText; App.state.filename = App.state.diffFileB; location.hash = "#/gate"; }
      }));
    } catch (e) {
      const out = $("#df-out");
      if (out) out.innerHTML = `<div class="err err-engine"><span class="e-kind">Backend failure</span><span class="err-msg">${esc(e.message || String(e))}</span></div>`;
      toast("Diff failed", true);
    }
  });
}

/* ── CI Gate ────────────────────────────────────────────────────────────── */
function renderGateResult(g) {
  const gate = g.gate || {};
  const res = g.result || {};
  const rdy = res.readiness || {};
  const counts = ((res.check || {}).counts) || {};
  const sup = res.support || {};
  const passed = !!gate.passed;
  let h = sectionTitle("Gate result", "policy evaluation against real evidence");
  h += `<div class="rdy-overall"><div><div class="ro-label">${esc(gate.policy || "")}</div><div class="ro-value">${statusBadge("pass_fail", passed ? "PASS" : "FAIL")}</div></div>
    <div style="margin-left:auto;text-align:right"><div class="ro-label">Exit code</div><div class="mono ro-value">${gate.exit_code ?? "-"}</div></div></div>`;
  h += metricRow([
    { label: "Errors", value: counts.errors ?? 0 },
    { label: "Warnings", value: counts.warnings ?? 0 },
    { label: "Readiness", value: rdy.overall || "-" },
    { label: "Trust", value: trustOf(sup) },
  ]);
  if (gate.reasons && gate.reasons.length) {
    h += sectionTitle(`Reasons (${gate.reasons.length})`, "why the gate did not pass");
    h += gate.reasons.map(r => `<div class="ilink"><span class="il-rule">GATE</span><span class="il-kind" style="color:var(--error)">FAIL</span><span class="il-a">${esc(r)}</span></div>`).join("");
  } else {
    h += `<p class="callout co-success"><span><strong>No gate reasons</strong> - the configured policy passed on the current evidence.</span></p>`;
  }
  h += `<p class="callout co-warning"><span><strong>CI PASS ≠ power-intent signoff</strong> - the gate reports whether the configured constraint policy passed. It is not a power/IR signoff.</span></p>`;
  h += `<div class="ilink"><span class="il-rule">JSON</span><span class="il-kind" style="color:var(--accent-2)">EVIDENCE</span><span class="il-a">Machine-readable gate result + analysis for CI or reporting.</span><span class="il-loc"><button class="btn btn-sm" id="gt-dl" type="button">Download</button></span></div>`;
  return h;
}

function wireGate(main) {
  const upfEl = $("#gt-upf");
  if (upfEl) upfEl.addEventListener("input", () => App.state.gateUpf = upfEl.value);
  const pick = $("#gt-pick");
  if (pick) pick.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".upf,.tcl,.txt";
    inp.addEventListener("change", async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      upfEl.value = await f.text();
      App.state.gateUpf = upfEl.value;
      App.state.filename = f.name;
      const fe = $("#gt-file"); if (fe) fe.textContent = f.name;
    });
    inp.click();
  });
  const samp = $("#gt-sample");
  if (samp) samp.addEventListener("click", async () => {
    try {
      upfEl.value = await fetchSample("cpu_v2");
      App.state.gateUpf = upfEl.value;
      App.state.filename = "cpu_subsys_v2.upf";
      const fe = $("#gt-file"); if (fe) fe.textContent = App.state.filename;
      toast("Regressed sample loaded - expect FAIL under STRICT");
    } catch (e) { toast(e.message, true); }
  });
  const useCur = $("#gt-use-current");
  if (useCur) useCur.addEventListener("click", () => {
    if (!App.state.upf) { toast("Run an analysis first, or load a sample", true); return; }
    upfEl.value = App.state.upf;
    App.state.gateUpf = App.state.upf;
    const fe = $("#gt-file"); if (fe) fe.textContent = App.state.filename;
  });
  const baseCur = $("#gt-base-current");
  if (baseCur) baseCur.addEventListener("click", () => {
    if (!App.state.analysis) { toast("Run an analysis first to use it as baseline", true); return; }
    $("#gt-baseline").value = JSON.stringify(App.state.analysis, null, 2);
    toast("Baseline set to current analysis");
  });
  const run = $("#gt-run");
  if (run) run.addEventListener("click", async () => {
    const content = (upfEl ? upfEl.value : "").trim();
    if (!content) { toast("Paste or load a candidate UPF first", true); return; }
    const baseText = ($("#gt-baseline") || {}).value || "";
    let baseline;
    if (baseText.trim()) {
      try { baseline = JSON.parse(baseText); }
      catch (e) { toast("Baseline is not valid JSON", true); return; }
    }
    const policy = $("#gt-policy").value;
    try {
      const g = await post("/api/gate", {
        content, policy, baseline: baseline || undefined,
        file: App.state.filename || "pasted.upf",
      });
      const out = $("#gt-out");
      if (out) out.innerHTML = renderGateResult(g);
      const dl = $("#gt-dl");
      if (dl) dl.addEventListener("click", () => {
        const payload = { gate: g.gate, result: g.result };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = "gate_result.json"; a.click();
        URL.revokeObjectURL(a.href); toast("Downloaded gate_result.json");
      });
    } catch (e) {
      const out = $("#gt-out");
      if (out) out.innerHTML = `<div class="err err-engine"><span class="e-kind">Backend failure</span><span class="err-msg">${esc(e.message || String(e))}</span></div>`;
      toast("Gate failed", true);
    }
  });
}

/* ── Reports ────────────────────────────────────────────────────────────── */
function wireReports(main) {
  const upfEl = $("#rp-upf");
  const netEl = $("#rp-netlist");
  if (upfEl) upfEl.addEventListener("input", () => App.state.reportUpf = upfEl.value);
  const pick = $("#rp-pick");
  if (pick) pick.addEventListener("click", () => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".upf,.tcl,.txt";
    inp.addEventListener("change", async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      upfEl.value = await f.text();
      App.state.reportUpf = upfEl.value;
      App.state.filename = f.name;
      const fe = $("#rp-file"); if (fe) fe.textContent = f.name;
    });
    inp.click();
  });
  const samp = $("#rp-sample");
  if (samp) samp.addEventListener("click", async () => {
    try {
      upfEl.value = await fetchSample("cpu_v2");
      App.state.reportUpf = upfEl.value;
      App.state.filename = "cpu_subsys_v2.upf";
      const fe = $("#rp-file"); if (fe) fe.textContent = App.state.filename;
      toast("Regressed sample loaded");
    } catch (e) { toast(e.message, true); }
  });
  const useCur = $("#rp-use-current");
  if (useCur) useCur.addEventListener("click", () => {
    if (!App.state.upf) { toast("Run an analysis first, or load a sample", true); return; }
    upfEl.value = App.state.upf;
    App.state.reportUpf = App.state.upf;
    const fe = $("#rp-file"); if (fe) fe.textContent = App.state.filename;
  });
  const run = $("#rp-run");
  if (run) run.addEventListener("click", async () => {
    const content = (upfEl ? upfEl.value : "").trim();
    if (!content) { toast("Paste or load a UPF file first", true); return; }
    const fmt = $("#rp-format").value;
    let design;
    const dt = (netEl && netEl.value.trim()) ? netEl.value.trim() : "";
    if (dt) {
      try { design = JSON.parse(dt); }
      catch (e) { toast("Design context is not valid JSON - run without it", true); return; }
    }
    try {
      const r = await post("/api/report", {
        content, format: fmt, design: design || undefined,
        file: App.state.filename || "pasted.upf",
      });
      const out = $("#rp-out");
      let html;
      if (fmt === "html") {
        html = `<div style="display:flex;gap:10px;margin:10px 0">
          <button class="btn btn-sm" id="rp-dl" type="button">Download .html</button>
          <button class="btn btn-sm" id="rp-open" type="button">Open in new tab</button>
        </div>
        <iframe class="report-frame" sandbox="" srcdoc="${escAttr(r.content)}" title="UPF-Insight report"></iframe>`;
      } else {
        html = `<div style="display:flex;gap:10px;margin:10px 0">
          <button class="btn btn-sm" id="rp-dl" type="button">Download .${fmt}</button>
        </div>
        <pre class="code-input" style="max-height:480px;overflow:auto;white-space:pre-wrap">${esc(r.content)}</pre>`;
      }
      out.innerHTML = html;
      const dl = $("#rp-dl");
      if (dl) dl.addEventListener("click", () => {
        const blob = new Blob([r.content], { type: fmt === "html" ? "text/html" : "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = `report.${fmt}`; a.click();
        URL.revokeObjectURL(a.href); toast(`Downloaded report.${fmt}`);
      });
      const op = $("#rp-open");
      if (op) op.addEventListener("click", () => {
        const w = window.open("", "_blank");
        if (w) { w.document.write(r.content); w.document.close(); }
      });
    } catch (e) {
      const out = $("#rp-out");
      if (out) out.innerHTML = `<div class="err err-engine"><span class="e-kind">Backend failure</span><span class="err-msg">${esc(e.message || String(e))}</span></div>`;
      toast("Report generation failed", true);
    }
  });
}

/* ── Home dashboard ─────────────────────────────────────────────────────── */
function wireHome(main) {
  main.querySelectorAll("[data-home-view]").forEach(btn => {
    btn.addEventListener("click", () => { location.hash = `#/${btn.dataset.homeView}`; });
  });
}

/* ── UPF Generator ──────────────────────────────────────────────────────── */
let genContent = "";
function wireGenerator(main) {
  const collect = (key) => {
    const keys = genFieldKeys(key);
    return [...(main.querySelectorAll(`.gen-rows[data-group="${key}"] .gen-param-row`) || [])].map(row => {
      const o = {};
      keys.forEach(k => { const el = row.querySelector(`[data-k="${k}"]`); o[k] = el ? el.value.trim() : ""; });
      return o;
    });
  };
  const val = (id, dflt) => { const el = $(id); return el ? el.value.trim() : dflt; };
  const pstStates = collect("pst_states").filter(s => s.name).map(s => {
    const states = {};
    s.states.split(/[\s,]+/).filter(Boolean).forEach(t => {
      const [k, v] = t.split(":");
      if (k && v) states[k.trim()] = v.trim();
    });
    return { name: s.name, states };
  });
  const buildParams = () => ({
    design_top: val("#g-top", "top"),
    upf_version: val("#g-ver", "3.0"),
    primary_power: val("#g-pp", "vdd"),
    primary_ground: val("#g-pg", "vss"),
    on_voltage: parseFloat(val("#g-onv", "1.0")) || 1.0,
    off_voltage: parseFloat(val("#g-offv", "0.0")) || 0.0,
    domains: collect("domains").filter(d => d.name),
    switches: collect("switches").filter(s => s.name),
    isolation: collect("isolation").filter(i => i.domain),
    level_shifters: collect("level_shifters").filter(l => l.domain),
    retention: collect("retention").filter(r => r.domain),
    repeaters: collect("repeaters").filter(r => r.domain),
    relations: collect("relations").filter(r => r.from_domain && r.to_domain),
    pst_states: pstStates,
    always_on: val("#g-aon", "").split(",").map(s => s.trim()).filter(Boolean),
    architecture: val("#g-arch", "flat"),
    hierarchy: val("#g-hier", "").split(",").map(s => s.trim()).filter(Boolean),
  });
  const setStatus = (html) => { const s = $("#g-status"); if (s) s.innerHTML = html; };
  const doGenerate = async () => {
    setStatus('<span class="gen-busy">generating…</span>');
    try {
      const res = await post("/api/generate", { params: buildParams() });
      if (res.architecture === "hierarchical") {
        const files = res.files || [];
        const first = files[0];
        genContent = (res.project || {})[first] || "";
        const tabs = files.map(f => `<button class="btn btn-sm gen-file-tab${f === first ? " gen-file-active" : ""}" data-file="${escAttr(f)}" type="button">${esc(f)}</button>`).join("");
        const bodies = files.map(f => `<div class="gen-file-body" data-file-body="${escAttr(f)}" style="${f === first ? "" : "display:none"}">${sourceViewer(((res.project || {})[f] || "").split("\n"))}</div>`).join("");
        $("#g-out").innerHTML = `<div class="gen-files" style="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0">${tabs}</div>${bodies}`;
        main.querySelectorAll(".gen-file-tab").forEach(b => b.addEventListener("click", () => {
          const f = b.dataset.file;
          main.querySelectorAll(".gen-file-tab").forEach(x => x.classList.toggle("gen-file-active", x === b));
          main.querySelectorAll(".gen-file-body").forEach(x => { x.style.display = x.dataset.fileBody === f ? "" : "none"; });
        }));
      } else {
        genContent = res.content || "";
        $("#g-out").innerHTML = sourceViewer(genContent.split("\n"));
      }
      const gval = $("#g-val");
      if (gval) gval.innerHTML = "";
      setStatus('<span class="gen-ok">generated</span>');
    } catch (e) { setStatus(`<span class="gen-bad">${esc(e.message)}</span>`); }
  };
  const doValidate = async () => {
    if (!genContent) { toast("Generate first"); return; }
    setStatus('<span class="gen-busy">validating…</span>');
    try {
      const res = await post("/api/validate", { content: genContent, file: "generated.upf" });
      const check = (res && res.check) || {};
      const findings = check.findings || [];
      const counts = check.counts || {};
      const errs = counts.errors ?? findings.filter(x => x.severity === "error").length;
      const warns = counts.warnings ?? findings.filter(x => x.severity === "warning").length;
      setStatus(`<span class="${errs ? "gen-bad" : "gen-ok"}">${errs}E</span> · <span class="gen-warn">${warns}W</span>`);
      const rows = findings.slice(0, 40).map(f => ({
        cells: [
          { html: `<span class="mono">${esc(f.rule)}</span>` },
          { html: statusBadge("severity", f.severity) },
          { html: `<span class="num mono">${f.line ?? "-"}</span>` },
          { html: `<span class="msg">${esc(f.message)}</span>` },
        ],
      }));
      const gval = $("#g-val");
      if (gval) gval.innerHTML = sectionTitle("Inline validation", `${findings.length} finding(s)`) +
        (rows.length ? `<div class="tbl-wrap"><table class="tbl"><thead><tr>
          <th>Rule</th><th>Severity</th><th>Line</th><th>Message</th></tr></thead><tbody>
          ${rows.map(r => `<tr>${r.cells.map(c => `<td>${c.html}</td>`).join("")}</tr>`).join("")}
        </tbody></table></div>` : '<p class="callout co-success"><span><strong>Clean</strong> - generated UPF passed within the supported scope.</span></p>') +
        `<div class="gen-next" style="margin-top:10px">` +
        `<span class="mono" style="font-size:11px;color:var(--text-muted);margin-right:8px">Next:</span>` +
        `<button class="btn btn-sm" data-gen-next="validator" type="button">Open in Validation →</button>` +
        `<button class="btn btn-sm" data-gen-next="gate" type="button">Run CI Gate →</button>` +
        `<button class="btn btn-sm" data-gen-next="diff" type="button">Compare against baseline →</button>` +
        `</div>`;
      main.querySelectorAll("[data-gen-next]").forEach(b => b.addEventListener("click", () => {
        const n = b.dataset.genNext;
        if (n === "validator") { App.state.upf = genContent; App.state.filename = "generated.upf"; location.hash = "#/validator"; }
        else if (n === "gate") { App.state.gateUpf = genContent; App.state.filename = "generated.upf"; location.hash = "#/gate"; }
        else if (n === "diff") { App.state.diffB = genContent; App.state.diffFileB = "generated.upf"; location.hash = "#/diff"; }
      }));
    } catch (e) { setStatus(`<span class="gen-bad">${esc(e.message)}</span>`); }
  };
  const gbtn = (id, fn) => { const el = $(id); if (el) el.addEventListener("click", fn); };
  gbtn("#g-gen", doGenerate);
  gbtn("#g-validate", doValidate);
  gbtn("#g-copy", async () => {
    if (!genContent) { toast("Generate first"); return; }
    try { await navigator.clipboard.writeText(genContent); toast("Copied"); } catch (e) { toast("Copy failed", true); }
  });
  gbtn("#g-dl", () => {
    if (!genContent) { toast("Generate first"); return; }
    const b = new Blob([genContent], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = "generated.upf"; a.click();
    URL.revokeObjectURL(a.href);
    toast("Downloaded generated.upf");
  });
  main.querySelectorAll(".gen-add").forEach(btn => btn.addEventListener("click", () => {
    const key = btn.dataset.group;
    const wrap = main.querySelector(`.gen-rows[data-group="${key}"]`);
    if (wrap) wrap.insertAdjacentHTML("beforeend", genEmptyRowHtml(key));
  }));
  main.querySelectorAll(".gen-rows").forEach(wrap => wrap.addEventListener("click", (e) => {
    const del = e.target.closest(".gen-del");
    if (del) del.closest(".gen-param-row").remove();
  }));
}

boot();
