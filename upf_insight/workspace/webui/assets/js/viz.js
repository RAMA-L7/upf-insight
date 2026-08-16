/* ═══════════════════════════════════════════════════════════════════════════
   UPF-Insight — viz.js
   Technical visualizations (mirrors the Ṛta viz.js style):
     - Background canvas (removed for the minimal tool aesthetic)
     - Readiness dimension rail (UPF dimensions)
     - Domain / supply network diagram
     - Supply coverage strips
     - PST state inventory
   All labels escaped; reduced-motion respected; monochrome ink only.
   ═══════════════════════════════════════════════════════════════════════════ */

import { esc } from "./theme.js";

/* ═══════════════════════════════════════════════════════════════════════════
   BACKGROUND — intentionally a no-op: the tool uses a plain white paper
   canvas. Kept as a stub so app.js's initBackground call is a safe no-op.
   ═══════════════════════════════════════════════════════════════════════════ */

export function initBackground(container) {
  if (!container) return;
  const canvas = container.querySelector("canvas");
  if (canvas) canvas.remove();
}

/* ═══════════════════════════════════════════════════════════════════════════
   READINESS RAIL — UPF signature dimension stack
   ═══════════════════════════════════════════════════════════════════════════ */

export function readinessRail(readiness) {
  const dims = readiness.dimensions || {};
  const names = ["POWER_STATES", "SUPPLY_NETWORK", "STRATEGIES", "CONSISTENCY", "DESIGN_CONTEXT"];
  const ink = { READY: "#1A1A1A", READY_WITH_ADVISORIES: "#1A1A1A", REVIEW_REQUIRED: "#555555", BLOCKED: "#000000", INSUFFICIENT_CONTEXT: "#8A8A8A", NOT_APPLICABLE: "#BBBBBB" };
  const fillOf = { READY: 1, READY_WITH_ADVISORIES: 0.85, REVIEW_REQUIRED: 0.5, BLOCKED: 0.25, INSUFFICIENT_CONTEXT: 0.1, NOT_APPLICABLE: 0.05 };
  const cells = names.map(n => {
    const key = Object.keys(dims).find(k => k.toUpperCase() === n);
    const d = key ? dims[key] : null;
    const status = d ? d.status : "NOT_APPLICABLE";
    const color = ink[status] || "#8A8A8A";
    const fill = fillOf[status] || 0.1;
    const summary = d && d.summary ? d.summary : "";
    return `<div class="rdy-dim" data-dim="${esc(n)}" tabindex="0" role="button" title="${escAttr(summary)}">
      <div class="rd-name">${esc(n.replace(/_/g, " "))}</div>
      <div class="rd-status"><span class="sdc-status sev-${status === "READY" || status === "READY_WITH_ADVISORIES" ? "success" : status === "REVIEW_REQUIRED" ? "warning" : status === "BLOCKED" ? "error" : status === "INSUFFICIENT_CONTEXT" ? "unknown" : "muted"}"><span class="sh ${status === "REVIEW_REQUIRED" ? "tri" : status === "READY" ? "circ" : ""}"></span>${esc(status.replace(/_/g, " "))}</span></div>
      <div class="rd-bar"><div class="rd-fill" style="width:${fill * 100}%;background:${color}"></div></div>
    </div>`;
  }).join("");
  return `<div class="rdy-rail">${cells}</div>`;
}

/* ═══════════════════════════════════════════════════════════════════════════
   SUPPLY COVERAGE STRIPS — bit-level (per domain element set)
   ═══════════════════════════════════════════════════════════════════════════ */

export function supplyStripHtml(name, segments, total) {
  const segW = 100 / Math.max(1, total);
  return `<div class="bus">
    <div class="bus-head"><span class="b-name">${esc(name)}</span><span class="b-status mono">${esc(total)} elements</span></div>
    <div class="bus-strip" aria-label="Supply coverage for ${escAttr(name)}">
      ${segments.map(s => `<div class="bus-bit ${s.status}" style="width:${s.count * segW}%" title="${escAttr(s.label)}"></div>`).join("")}
    </div>
  </div>`;
}

/* ═══════════════════════════════════════════════════════════════════════════
   PST STATE INVENTORY — per supply-state cell
   ═══════════════════════════════════════════════════════════════════════════ */
export function pstMatrixHtml(pst) {
  if (!pst || !pst.states) return "";
  const states = pst.states || [];
  const supplies = [...new Set(states.flatMap(s => Object.keys(s.supply_states || {})))];
  if (!supplies.length) return "";
  const cellCls = (v) => v === "ON" ? "ps-on" : v === "OFF" ? "ps-off" : v ? "ps-other" : "ps-missing";
  let h = '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>PST state</th>' +
    supplies.map(s => `<th>${esc(s)}</th>`).join("") + "</tr></thead><tbody>";
  states.forEach(s => {
    h += `<tr><td class="mono">${esc(s.name)}</td>` +
      supplies.map(sup => {
        const v = (s.supply_states || {})[sup];
        return `<td><span class="ps-cell ${cellCls(v)}">${esc(v || "—")}</span></td>`;
      }).join("") + "</tr>";
  });
  h += "</tbody></table></div>";
  return h;
}

function escAttr(v) {
  return String(v == null ? "" : v).replace(/"/g, "&quot;").replace(/</g, "&lt;");
}
