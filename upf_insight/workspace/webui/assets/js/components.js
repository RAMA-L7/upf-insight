/* ═══════════════════════════════════════════════════════════════════════════
   UPF-Insight — components.js
   Product component builders (shared with the Ṛta design system). ALL
   user-controlled values are escaped via theme.esc.
   ═══════════════════════════════════════════════════════════════════════════ */

import { esc, statusBadge, severityClass } from "./theme.js";

/* ── Page title system ──────────────────────────────────────────────────── */
export function pageHead(section, title, purpose = "", next = "") {
  return `<div class="page">
    <p class="page-eyebrow">${esc(section)}</p>
    <h1 class="page-title">${esc(title)}</h1>
    ${purpose ? `<p class="page-purpose">${esc(purpose)}</p>` : ""}
    ${next ? `<p class="page-next"><span class="pn-label">Next</span> ${esc(next)}</p>` : ""}`;
}

export function sectionTitle(label, note = "") {
  return `<h2 class="section-title">${esc(label)}${note ? ` <span class="st-note">${esc(note)}</span>` : ""}</h2>`;
}

/* ── Metrics (compact rail, not cards) ──────────────────────────────────── */
export function metricRow(items) {
  return `<div class="metric-row">${items.map(m =>
    `<div class="metric"><div class="m-num">${esc(m.value)}</div><div class="m-label">${esc(m.label)}</div></div>`
  ).join("")}</div>`;
}

export function chips(items) {
  if (!items || !items.length) return "";
  return `<div class="chips">${items.join("")}</div>`;
}

/* ── Empty states ───────────────────────────────────────────────────────── */
export function emptyState(title, meaning, next = "") {
  return `<div class="empty">
    <div class="e-mark">// analysis</div>
    <div class="e-title">${esc(title)}</div>
    <p class="e-meaning">${esc(meaning)}</p>
    ${next ? `<p class="e-next">${esc(next)}</p>` : ""}
  </div>`;
}

/* ── Typed error states ─────────────────────────────────────────────────── */
export function typedError(kind, message) {
  const cls = {
    invalid: "err-invalid", insufficient: "err-insufficient",
    incompatible: "err-incompatible", engine: "err-engine",
  }[kind] || "err-engine";
  const label = {
    invalid: "Invalid input", insufficient: "Insufficient context",
    incompatible: "Incompatible baseline", engine: "Engine failure",
  }[kind] || "Error";
  return `<div class="err ${cls}"><span class="e-kind">${esc(label)}</span><span class="err-msg">${esc(message)}</span></div>`;
}

export function callout(message, kind = "info") {
  const cls = { error: "co-error", warning: "co-warning", info: "co-info", success: "co-success" }[kind] || "co-info";
  return `<div class="callout ${cls}"><span>${message}</span></div>`;
}

/* ── Source viewer with highlights ──────────────────────────────────────── */
export function sourceViewer(lines, highlights = {}, focusLines = []) {
  if (!lines || !lines.length) return "";
  const out = ['<div class="src">'];
  lines.forEach((line, i) => {
    const n = i + 1;
    let cls = highlights[n] || "";
    let conn = "";
    if (focusLines.includes(n)) {
      cls = cls + " hl";
      conn = focusLines.length > 1 ? "↕" : "";
    }
    out.push(`<div class="src-line ${cls}"><span class="src-no">${n}</span><span class="src-text">${esc(line)}</span>${conn ? `<span class="conn">${conn}</span>` : ""}</div>`);
  });
  out.push("</div>");
  return out.join("");
}

export function sourceExcerpt(lines, linesToShow, focusLines = []) {
  if (!linesToShow.length) return "";
  const lo = Math.max(1, Math.min(...linesToShow) - 2);
  const hi = Math.min(lines.length, Math.max(...linesToShow) + 2);
  const slice = lines.slice(lo - 1, hi);
  const hl = {};
  linesToShow.forEach(n => { if (n >= lo && n <= hi) hl[n] = "hl"; });
  return sourceViewer(slice, hl, linesToShow.filter(n => n >= lo && n <= hi));
}

/* ── Generic dense table ────────────────────────────────────────────────── */
export function table(headers, rows, { mono = true, clickable = false, selectedKey = null } = {}) {
  const th = headers.map(h => `<th>${esc(h.label)}</th>`).join("");
  const trs = rows.map(r => {
    const click = clickable ? ` class="row-click${r.key && r.key === selectedKey ? " row-selected" : ""}" data-key="${escAttr(r.key || "")}"${r.idx != null ? ` data-idx="${r.idx}"` : ""}` : "";
    const tds = r.cells.map(c => {
      if (typeof c === "object" && c.html) return `<td class="${c.cls || ""}">${c.html}</td>`;
      return `<td class="${c.cls || ""}">${esc(c)}</td>`;
    }).join("");
    return `<tr${click}>${tds}</tr>`;
  }).join("");
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`;
}

function escAttr(v) {
  return String(v == null ? "" : v).replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

/* ── Accordion ──────────────────────────────────────────────────────────── */
export function accordion(title, bodyHtml, { open = false, badge = "" } = {}) {
  return `<details class="acc"${open ? " open" : ""}><summary>${esc(title)} ${badge}</summary><div class="acc-body">${bodyHtml}</div></details>`;
}

/* ── Key-value list ─────────────────────────────────────────────────────── */
export function kvList(entries) {
  return `<dl class="kv">${entries.map(([k, v]) =>
    `<dt>${esc(k)}</dt><dd>${v == null ? "—" : esc(v)}</dd>`).join("")}</dl>`;
}

/* ── Segmented filter ───────────────────────────────────────────────────── */
export function segFilter(name, options, active) {
  return `<div class="seg" role="group" aria-label="${escAttr(name)}">${options.map(o =>
    `<button type="button" data-seg="${escAttr(o)}" class="${o === active ? "active" : ""}">${esc(o)}</button>`
  ).join("")}</div>`;
}

/* ── Finding row (inspector-friendly click row) ─────────────────────────── */
export function findingRow(it) {
  const badge = statusBadge("severity", it.sev);
  return `<tr class="row-click finding-row" data-idx="${it._i}" data-key="${escAttr(it.code)}">
    <td>${badge}</td>
    <td class="mono">${esc(it.code)}</td>
    <td class="msg">${esc(it.msg)}</td>
    <td class="mono">${esc(it.obj || "")}</td>
    <td class="mono">${esc(it.loc || "")}</td>
  </tr>`;
}

export function findingDetailHtml(it, rule) {
  const parts = [];
  parts.push(`<div style="display:flex;gap:8px;align-items:center;margin-bottom:10px">${statusBadge("severity", it.sev)}<span class="mono" style="color:var(--text-secondary)">${esc(it.code)}</span></div>`);
  parts.push(`<p style="margin:0 0 10px;font-size:14px;color:var(--text-primary)">${esc(it.msg)}</p>`);
  const meta = [];
  if (it.obj) meta.push(["Object", it.obj]);
  if (it.loc) meta.push(["Location", it.loc]);
  if (it.line2) meta.push(["Provenance", `L${it.line} ↔ L${it.line2}`]);
  if (meta.length) parts.push(`<div class="insp-section"><div class="insp-k">Context</div>${kvList(meta)}</div>`);
  if (rule) {
    if (rule.title) parts.push(`<div class="insp-section"><div class="insp-k">Rule</div><div class="insp-v" style="font-weight:600">${esc(rule.title)}</div></div>`);
    if (rule.layer) parts.push(`<div class="insp-section"><div class="insp-k">Layer</div><div class="insp-v mono">${esc(rule.layer)}</div></div>`);
    if (rule.description) parts.push(`<div class="insp-section"><div class="insp-k">Why it matters</div><div class="insp-v">${esc(rule.description)}</div></div>`);
  }
  return parts.join("");
}
