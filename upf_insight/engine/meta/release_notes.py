"""Release notes for the ``upf-insight whats-new`` command.

This module ships inside the wheel, so ``upf-insight whats-new`` works
offline in any environment - it does not need the git repo or a network
connection. Keep in sync with CHANGELOG.md: append the new version here on
every release (newest first).
"""

from ... import __version__ as _APP_VERSION

#: version -> list of bullet lines describing what changed in that release.
RELEASE_NOTES: dict[str, list[str]] = {
    "0.3.0": [
        "Design-aware netlist parsing: load_design() accepts Verilog (.v/.sv) "
        "in addition to the JSON design snapshot - ports, instances, buses, "
        "and sequential elements are parsed structurally with no EDA tool.",
        "Netlist-aware port coverage: analyze_design_coverage() buckets "
        "inputs/outputs as CONSTRAINED/UNCONSTRAINED/PARTIAL against UPF port "
        "attributes; surfaced in validate results, 'analyze', and the API.",
        "Strategy interaction analysis: new rules UPF-085 (duplicate strategy), "
        "UPF-086 (overriding/conflicting strategy - overlapping switch outputs, "
        "contradictory locations, redefined retention).",
        "Wildcard risk analysis: new rule UPF-087 flags low-specificity "
        "wildcard patterns with a 0-10 risk score and honest elaboration-time "
        "disclaimer.",
        "New CLI commands: 'analyze' (one-shot end-to-end analysis with "
        "combined HTML report), 'batch check|report' (directory-wide runs), "
        "'lint' (--check/--fix reformatter), 'convert' (UPF to JSON/YAML), "
        "and 'rules show CODE' with severity/search filters.",
        "Custom rule sets: declarative YAML rules (--custom-rules) let teams "
        "enforce house style alongside the built-in registry.",
        "MCP server: 'upf-insight-mcp' exposes 19 deterministic tools over "
        "JSON-RPC stdio for agent integration while keeping the engine "
        "LLM-free. One tool per CLI/API feature: validate, model, pst, "
        "coverage, relations, analyze, report, diff, generate, rules, "
        "rule_show, rules_audit, gate, batch, lint, convert, quality, "
        "whats_new and version.",
        "CI hardening: GitHub Actions workflow (3-OS x Python 3.10-3.12), "
        "reusable upf-gate composite action, pre-commit hook for staged "
        ".upf/.tcl files, evidence manifest and golden runner scripts.",
    ],
    "0.2.4": [
        "Semantic hardening: cascade suppression - dependent rules declare "
        "error prerequisites (depends_on) and are downgraded to info with a "
        "blocked_by tag when the prerequisite errors on the same subject, so "
        "secondary findings never masquerade as definitive errors.",
        "Rule metadata audit: every rule now carries semantic_inputs, a design "
        "context (UPF_ONLY/NETLIST_REQUIRED/PARTIAL), and a test_ref. New "
        "'upf-insight rules audit' command verifies registry/handler sync, "
        "dependency integrity, and deterministic ordering across all 74 rules.",
        "Evidence boundary enforced: a fact requiring a netlist is never "
        "reported as an error (NETLIST_REQUIRED errors are downgraded to "
        "warnings). UNKNOWN is not FALSE - new evidence-boundary suite proves "
        "unknown crossings and missing-isolation risks stay honest advisories.",
        "New 'upf-insight quality' command runs the canonical 42-mutation "
        "corpus and reports detection rate, precision (error-level and "
        "overall), baseline false positives, and per-category breakdown in "
        "text or JSON. The regression suite now consumes the same corpus from "
        "engine/quality.py - one source of truth.",
    ],
    "0.2.3": [
        "Adversarial coverage expansion: 42 deliberate semantic defects "
        "across 11 categories (supply topology, power switch, level shifting, "
        "isolation, retention, always-on, PST, duplicates, supply "
        "connectivity, relations, unsupported syntax) - mutation detection "
        "rate 42/42 with zero false positives on the clean baseline.",
        "Parser fix: set_port_attributes now parses every target name, so "
        "switch/retention/isolation controls are recognized as always-on "
        "(surfaced real UPF-071/047/051 findings previously masked); UPF-051 "
        "compares retention controls by signal name, removing a clean-"
        "baseline false positive.",
        "New rules: UPF-065 (ground wired to a switch output - error), "
        "UPF-077 (switch with no control port - error), UPF-078 (retention on "
        "a switchable domain with no retention supply - error), UPF-079 "
        "(level-shifter threshold outside every known supply voltage - "
        "warning). Now 74 rules in the registry.",
        "UPF-060 is voltage-aware: an equal-voltage crossing with a declared "
        "level shifter is flagged unnecessary (warning); unknown voltages "
        "stay an info advisory.",
    ],
    "0.2.2": [
        "Adversarial semantic validation (mutation testing): 12 new tests "
        "prove the validator catches intentionally broken power intent, not "
        "just generated designs - clean baseline plus 9 deliberate mutations "
        "each detected by the expected rule (mutation detection rate 9/9).",
        "New rule UPF-039 (impossible PST state): a row with a switch output "
        "ON while its input supply is OFF is physically impossible - now 68 "
        "rules in the registry.",
        "UPF-073 upgraded from info to error: a switch output consumed by no "
        "power domain means the switchable domain is not powered by the "
        "switch - a real defect, not an advisory.",
        "UPF-053 is now sense-aware: parses {name sense} retention controls "
        "and flags save/restore on the same signal with the same sense "
        "(cannot sequence) vs. opposite senses (the canonical IEEE 1801 "
        "pattern).",
        "SHA-256 determinism regression: the same input produces byte-"
        "identical UPF every run.",
    ],
    "0.2.1": [
        "Generator semantic hardening from an independent IEEE 1801 audit: a "
        "switchable domain's primary supply is now the switch output "
        "(vdd -> switch -> vdd_sw_out -> core), so power-gated domains are "
        "truly gated.",
        "Per-domain voltage grounds the PST ON values and level-shifter "
        "thresholds; the validator's UPF-061 now detects a real different-"
        "voltage crossing without a shifter. CLI: --domain-voltage.",
        "Isolation now emits explicit -applies_to outputs, and level shifters "
        "emit -applies_to both - boundary direction is never a silent UPF "
        "default.",
        "Isolation and level shifters on switchable domains are placed at "
        "parent (always-on side), not self, so they keep their supply when the "
        "domain powers down (resolves UPF-063).",
        "Retention names explicit elements (-elements {regA regB}) and "
        "save/restore with active sense (-save_signal {save high} / "
        "-restore_signal {restore low}). CLI: --retention-spec.",
        "Meaningful default PST: ALL_ON plus one sw.<name>.off per switch "
        "(VDD ON, switch output OFF). The physically impossible PS_OFF (VDD "
        "OFF while the switch output is ON) is gone, and unused port states "
        "are no longer declared (no UPF-030 on generated output).",
        "Generator UI: Voltage column on domains, Applies-to on isolation and "
        "level shifters, Save/restore sense + Elements on retention.",
    ],
    "0.2.0": [
        "Flat + hierarchical power-intent sprint: Flat UPF and Hierarchical UPF "
        "are now first-class in both the generator and validation. The generator "
        "has an architecture selector (Flat / Hierarchical), per-domain power "
        "types (always_on / switchable, never inferred), a domain-relation "
        "editor, per-child domain ownership and load_upf supply mapping.",
        "Generated flat and hierarchical projects round-trip through validation "
        "and produce the same architecture, domain, supply, hierarchy, relation, "
        "topology and provenance model - verified end-to-end from the CLI.",
        "New canonical Power Domain Relation Matrix derived from the engine "
        "model (ISO / LS / ISO+LS / RET / SW / CTRL) with per-relation "
        "provenance; supply sharing is a separate network view and never a "
        "matrix cell.",
        "Hierarchy analysis: domain ownership (UPF file, scope, owner), "
        "flat-vs-hierarchical architecture detection, and load_upf supply maps "
        "with parent-scope resolution (no more false undefined-supply findings).",
        "Scope-aware supply resolution and per-strategy scope provenance fix "
        "cross-scope relations in child UPF files (same-named supplies in "
        "sibling scopes never cross-resolve).",
        "New validation rules: UPF-099 (supply-map side undefined) and "
        "UPF-100 (loaded UPF file missing), both with provenance.",
        "CLI: upf-insight relations FILE... [--json], generate --architecture "
        "hierarchical with --domain-type/--domain-power/--switch/--relation, "
        "and reports expose architecture, relations, supply sharing, hierarchy "
        "and supply maps in text, JSON and HTML.",
    ],
    "0.1.0": [
        "Initial validation candidate: deterministic UPF power-intent "
        "validation with 67+ rules, readiness scoring, structural coverage, "
        "semantic diff, CI gate (exit 0/1/2/3), HTML/JSON reports and the "
        "feature-first web workspace with Test Drive.",
    ],
}


def latest_version() -> str:
    """Return the newest version with release notes (deterministic)."""
    return max(RELEASE_NOTES)


def installed_version() -> str:
    """Return the installed package version."""
    return _APP_VERSION
