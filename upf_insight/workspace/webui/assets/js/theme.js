/* ═══════════════════════════════════════════════════════════════════════════
   UPF-Insight - theme.js
   Escaping + status metadata + design tokens.
   Mirrors the sdc-tools (Ṛta) ui/theme.py contract so the workspace shares the
   same design system. Every user-controlled value is escaped at render time.
   ═══════════════════════════════════════════════════════════════════════════ */

export function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function escAttr(value) {
  return esc(value);
}

/* Fallback status metadata - shared vocabulary with Ṛta so the UI is never
   empty if /api/design is slow; the API response replaces it when it arrives. */
const FALLBACK = {
  severity: {
    fatal:   { label: "FATAL",   color: "error",  shape: "octagon" },
    error:   { label: "ERROR",   color: "error",  shape: "octagon" },
    warning: { label: "WARNING", color: "warning", shape: "triangle" },
    info:    { label: "INFO",    color: "info",   shape: "circle" },
  },
  trust: {
    VALIDATED:              { label: "VALIDATED",  color: "success", shape: "square" },
    PARTIALLY_VALIDATED:    { label: "PARTIAL",    color: "warning", shape: "square-half" },
    NETLIST_REQUIRED:       { label: "NETLIST",    color: "info",    shape: "square-net" },
    TCL_EXECUTION_REQUIRED: { label: "TCL EXEC",   color: "unknown", shape: "square-term" },
    UNSUPPORTED:            { label: "UNSUPPORTED", color: "error",  shape: "slash" },
    NOT_VALIDATED:          { label: "NOT CHECKED", color: "unknown", shape: "square-hollow" },
  },
  readiness: {
    READY:                 { label: "READY",   color: "success", shape: "shield" },
    READY_WITH_ADVISORIES: { label: "READY+",  color: "success", shape: "shield-dot" },
    REVIEW_REQUIRED:       { label: "REVIEW",  color: "warning", shape: "triangle" },
    BLOCKED:               { label: "BLOCKED", color: "error",   shape: "octagon" },
    INSUFFICIENT_CONTEXT:  { label: "LIMITED", color: "unknown", shape: "shield-hollow" },
    NOT_APPLICABLE:        { label: "N/A",     color: "muted",   shape: "square-hollow" },
  },
  diff: {
    NEW:       { label: "NEW",       color: "success", shape: "diamond" },
    RESOLVED:  { label: "RESOLVED",  color: "info",    shape: "circle" },
    CHANGED:   { label: "CHANGED",   color: "warning", shape: "triangle" },
    UNCHANGED: { label: "UNCHANGED", color: "muted",   shape: "square" },
  },
  pass_fail: {
    PASS: { label: "PASS", color: "success", shape: "circle" },
    FAIL: { label: "FAIL", color: "error",   shape: "octagon" },
  },
};

const COLOR_MAP = {
  success: "sev-success", warning: "sev-warning", error: "sev-error",
  info: "sev-info", unknown: "sev-unknown", muted: "sev-muted",
};

export const STATUS = { ...FALLBACK };

export function setStatusMeta(meta) {
  if (!meta) return;
  for (const kind of ["severity", "trust", "readiness", "diff", "pass_fail"]) {
    if (meta[kind] && typeof meta[kind] === "object") {
      STATUS[kind] = { ...STATUS[kind], ...meta[kind] };
    }
  }
}

export function statusMeta(kind, status) {
  const table = STATUS[kind] || {};
  const s = String(status == null ? "" : status).toUpperCase();
  if (table[s]) return table[s];
  return { label: status == null || status === "" ? "-" : String(status), color: "muted", shape: "square" };
}

export function statusBadge(kind, status) {
  const m = statusMeta(kind, status);
  const color = COLOR_MAP[m.color] || "sev-muted";
  const shape = m.shape || "square";
  const shapeCls = shape.includes("tri") ? "tri"
    : shape.includes("circ") ? "circ"
    : shape.includes("diam") ? "diam" : "";
  return `<span class="sdc-status ${color}"><span class="sh ${shapeCls}"></span>${esc(m.label)}</span>`;
}

export function severityClass(sev) {
  return COLOR_MAP[(STATUS.severity[sev] || {}).color] || "sev-muted";
}

/* Tokens (mirror Ṛta COLORS) - set from /api/design when available.
   Monochrome ink: pure white canvas, black accent, grey scale. */
export const TOKENS = {
  colors: {
    background_primary: "#FFFFFF", background_secondary: "#FAFAFA",
    surface: "#FFFFFF", surface_elevated: "#FFFFFF", surface_overlay: "#FFFFFF",
    border_subtle: "#E6E6E6", border_active: "#C9C9C9",
    text_primary: "#000000", text_secondary: "#333333", text_muted: "#808080",
    accent_primary: "#000000", accent_secondary: "#000000",
    success: "#1A1A1A", warning: "#555555", error: "#000000", info: "#2E2E2E",
    unknown: "#8A8A8A", not_applicable: "#AAAAAA", focus: "#000000",
  },
};

export function setTokens(meta) {
  if (meta && meta.colors) Object.assign(TOKENS.colors, meta.colors);
}

export function color(name) {
  return TOKENS.colors[name] || "#68738A";
}
