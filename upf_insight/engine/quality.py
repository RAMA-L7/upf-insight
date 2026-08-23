"""Validation quality metrics - detection rate and precision.

Runs the canonical adversarial mutation corpus against the validator and
reports the two numbers that matter for a deterministic validation product:

    detection rate = detected defects / injected defects
    precision      = correct findings / total findings

The mutation corpus (clean baseline + one-defect-per-mutation texts) lives
here so the CLI ``quality`` report, the web API, and the regression suite all
consume the SAME corpus - there is no test-only copy that can drift from what
the product reports.

Definitions
-----------
* detected: the mutation's expected rule appears among the findings *added*
  relative to the clean baseline (message-level, so cascade noise cannot fake
  a detection).
* correct finding: an added finding whose rule equals the mutation's expected
  rule.
* total findings: every finding added relative to the baseline across all
  mutation runs (extra cascade/dependent findings therefore lower precision,
  honestly).
* baseline false positives: error-severity findings on the clean baseline -
  must be zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..generate.generator import (
    UPFParams, DomainParam, SwitchParam, IsolationParam,
    LevelShifterParam, RetentionParam, generate_upf,
)
from ..preprocess.upf_preprocess import preprocess
from .engine import validate_records


def clean_baseline() -> str:
    """Known-good generated design: switchable core on a switched supply,
    isolation + level shifter at parent, retention with elements, a PST with
    real ALL_ON + sw.off states, and always-on controls."""
    p = UPFParams(
        design_top="top",
        domains=[
            DomainParam("core", elements="u_core", primary_power="vdd_sw_out",
                        voltage="0.8", domain_type="switchable"),
            DomainParam("io", elements="u_io", voltage="1.0",
                        domain_type="always_on"),
            DomainParam("sram", elements="u_sram", voltage="1.0",
                        domain_type="always_on"),
        ],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out", "pwr_en")],
        isolation=[IsolationParam("core", clamp_value="0", signal="iso_en")],
        level_shifters=[LevelShifterParam("core", rule="low_to_high",
                                          threshold="0.8")],
        retention=[RetentionParam("core", elements="regA regB")],
        always_on=["clk", "rst", "save", "restore", "iso_en", "pwr_en"],
    )
    return generate_upf(p)


BASE = clean_baseline()

ISO_BLOCK = (
    "set_isolation iso_core \\\n"
    "    -domain core \\\n"
    "    -isolation_supply vdd_iso \\\n"
    "    -clamp_value 0 \\\n"
    "    -applies_to outputs \\\n"
    "    -location parent\n"
)
LS_BLOCK = (
    "set_level_shifter ls_core \\\n"
    "    -domain core \\\n"
    "    -location parent \\\n"
    "    -threshold 0.8 \\\n"
    "    -applies_to both \\\n"
    "    -rule low_to_high\n"
)

#: (category, mutation name, mutated UPF text, expected rule)
MUTATIONS: List[Tuple[str, str, str, str]] = [
    # ---- Supply topology ----
    ("supply", "break switched supply",
     BASE.replace("-primary_power_net vdd_sw_out", "-primary_power_net vdd", 1), "UPF-073"),
    ("supply", "disconnect switch output",
     BASE.replace("-primary_power_net vdd_sw_out", "-primary_power_net vdd_other", 1), "UPF-073"),
    ("supply", "orphan supply net",
     BASE + "create_supply_net orphan_vdd -resolve net\n", "UPF-022"),
    ("supply", "unknown ground reference",
     BASE.replace("-primary_ground_net vss", "-primary_ground_net vss_ghost", 1), "UPF-010"),
    ("supply", "ground tied to switch output",
     BASE.replace("-primary_ground_net vss", "-primary_ground_net vdd_sw_out", 1), "UPF-065"),
    # ---- Power switch ----
    ("switch", "switch without control port",
     BASE.replace("    -control_port pwr_en \\\n", ""), "UPF-077"),
    ("switch", "wrong ON condition",
     BASE.replace("-on_state {on {vdd} {pwr_en}}", "-on_state {on {vdd} {bogus_sig}}"), "UPF-074"),
    ("switch", "wrong OFF condition",
     BASE.replace("-off_state {off {vdd} {!pwr_en}}", "-off_state {off {vdd} {!bogus_sig}}"), "UPF-074"),
    ("switch", "identical ON/OFF conditions",
     BASE.replace("-off_state {off {vdd} {!pwr_en}}", "-off_state {off {vdd} {pwr_en}}"), "UPF-075"),
    ("switch", "switch without off-state",
     BASE.replace("    -on_state {on {vdd} {pwr_en}} \\\n    -off_state {off {vdd} {!pwr_en}}\n",
                  "    -on_state {on {vdd} {pwr_en}}\n"), "UPF-076"),
    ("switch", "switch control not always-on",
     BASE.replace("set_port_attributes clk, rst, save, restore, iso_en, pwr_en ",
                  "set_port_attributes clk, rst, save, restore, iso_en "), "UPF-071"),
    ("switch", "undefined switch input supply",
     BASE.replace("    -input_supply_port vdd \\\n", "    -input_supply_port vdd_ghost \\\n"), "UPF-070"),
    ("switch", "undefined switch output supply",
     BASE.replace("    -output_supply_port vdd_sw_out \\\n", "    -output_supply_port vdd_ghost_out \\\n"), "UPF-070"),
    # ---- Voltage crossing / level shifting ----
    ("level-shift", "remove level shifter",
     BASE.replace(LS_BLOCK, ""), "UPF-061"),
    ("level-shift", "wrong LS direction",
     BASE.replace("-rule low_to_high", "-rule high_to_low"), "UPF-062"),
    ("level-shift", "LS threshold outside voltage range",
     BASE.replace("-threshold 0.8", "-threshold 1.7"), "UPF-079"),
    ("level-shift", "LS on equal-voltage crossing",
     BASE.replace("-state {ON 0.8}", "-state {ON 1.0}"), "UPF-060"),
    # ---- Isolation ----
    ("isolation", "remove isolation",
     BASE.replace(ISO_BLOCK, ""), "UPF-042"),
    ("isolation", "isolation at self in switchable domain",
     BASE.replace("-applies_to outputs \\\n    -location parent",
                  "-applies_to outputs \\\n    -location self"), "UPF-041"),
    ("isolation", "invalid clamp value",
     BASE.replace("-clamp_value 0", "-clamp_value banana"), "UPF-046"),
    ("isolation", "isolation moved to always-on domain (wrong direction)",
     BASE.replace("    -domain core \\\n    -isolation_supply vdd_iso",
                  "    -domain io \\\n    -isolation_supply vdd_iso"), "UPF-042"),
    ("isolation", "missing isolation control",
     BASE.replace("set_isolation_control iso_core \\\n    -domain core \\\n"
                  "    -isolation_signal iso_en \\\n    -isolation_sense high\n", ""), "UPF-045"),
    # ---- Retention ----
    ("retention", "retention without elements",
     BASE.replace("\\\n    -elements {regA regB}", ""), "UPF-052"),
    ("retention", "save/restore same sense",
     BASE.replace("-save_signal {save high} \\\n    -restore_signal {restore low}",
                  "-save_signal {ret_en high} \\\n    -restore_signal {ret_en high}"), "UPF-053"),
    ("retention", "retention without supply on switchable domain",
     BASE.replace("    -retention_supply retention \\\n", ""), "UPF-078"),
    ("retention", "retention without control",
     BASE.replace("set_retention_control ret_core \\\n    -domain core \\\n"
                  "    -save_signal {save high} \\\n    -restore_signal {restore low}\n", ""), "UPF-054"),
    ("retention", "retention control not always-on",
     BASE.replace("set_port_attributes clk, rst, save, restore, iso_en, pwr_en ",
                  "set_port_attributes clk, rst, iso_en, pwr_en "), "UPF-051"),
    # ---- Always-on ----
    ("always-on", "always-on attributes removed",
     BASE.replace("set_port_attributes clk, rst, save, restore, iso_en, pwr_en -attribute {always_on true}\n", ""), "UPF-047"),
    ("always-on", "always-on domain on switched supply",
     BASE.replace("set_domain_supply_net io \\\n    -primary_power_net vdd \\\n",
                  "set_domain_supply_net io \\\n    -primary_power_net vdd_sw_out \\\n"), "UPF-061"),
    # ---- PST ----
    ("pst", "impossible switch state (output ON, input OFF)",
     BASE.replace("add_pst_state ALL_ON \\\n    -pst pst_top \\\n    -state {vdd ON vss ON vdd_sw_out ON}",
                  "add_pst_state BROKEN \\\n    -pst pst_top \\\n    -state {vdd OFF vss ON vdd_sw_out ON}"), "UPF-039"),
    ("pst", "always-on supply OFF in a state",
     BASE.replace("add_pst_state ALL_ON \\\n    -pst pst_top \\\n    -state {vdd ON vss ON vdd_sw_out ON}",
                  "add_pst_state BROKEN \\\n    -pst pst_top \\\n    -state {vdd OFF vss ON vdd_sw_out OFF}"), "UPF-031"),
    ("pst", "undefined supply in PST row",
     BASE.replace("add_pst_state sw_core.off \\\n    -pst pst_top \\\n    -state {vdd ON vss ON vdd_sw_out OFF}",
                  "add_pst_state sw_core.off \\\n    -pst pst_top \\\n"
                  "    -state {vdd ON vss ON vdd_sw_out OFF vdd_ghost ON}"), "UPF-031"),
    ("pst", "no OFF state for switchable supply",
     BASE.replace("add_pst_state sw_core.off \\\n    -pst pst_top \\\n    -state {vdd ON vss ON vdd_sw_out OFF}\n", ""), "UPF-030"),
    # ---- Duplicate definitions ----
    ("duplicate", "duplicate power domain",
     BASE + "create_power_domain core\n", "UPF-013"),
    ("duplicate", "duplicate supply net",
     BASE + "create_supply_net vdd -resolve port\n", "UPF-022"),
    ("duplicate", "duplicate power switch",
     BASE + "create_power_switch sw_core -domain core -input_supply_port vdd "
            "-output_supply_port vdd_sw_out -control_port pwr_en\n", "UPF-013"),
    # ---- Supply connectivity ----
    ("supply-connectivity", "supply set without power/ground function",
     BASE + "create_supply_set empty_ss\n", "UPF-023"),
    ("supply-connectivity", "connect to unknown port",
     BASE.replace("connect_supply_net vdd -ports vdd\n",
                  "connect_supply_net vdd -ports vdd_ghost\n"), "UPF-024"),
    # ---- Domain relationships ----
    ("relations", "strategy references unknown domain",
     BASE + "set_isolation iso_ghost -domain ghost_domain -isolation_supply vdd_iso\n", "UPF-011"),
    ("relations", "level shifter on unknown domain",
     BASE + "set_level_shifter ls_ghost -domain ghost_domain -location parent\n", "UPF-011"),
    # ---- Unsupported syntax ----
    ("unsupported", "unknown command",
     BASE + "frobnicate_power_domain foo\n", "UPF-001"),
    ("unsupported", "unknown option on known command",
     BASE.replace("create_power_domain core", "create_power_domain core -bogus_option x"), "UPF-002"),
]

CATEGORIES = [
    "supply", "switch", "level-shift", "isolation", "retention",
    "always-on", "pst", "duplicate", "supply-connectivity",
    "relations", "unsupported",
]


@dataclass
class QualityReport:
    """Structured quality metrics for the mutation corpus."""

    total_mutations: int = 0
    detected: int = 0
    missed: List[Tuple[str, str, str]] = field(default_factory=list)  # (cat, name, expected)
    baseline_errors: int = 0
    baseline_false_positives: int = 0
    correct_findings: int = 0
    total_findings: int = 0
    correct_errors: int = 0
    total_errors: int = 0
    per_category: Dict[str, dict] = field(default_factory=dict)

    @property
    def detection_rate(self) -> float:
        if self.total_mutations == 0:
            return 0.0
        return self.detected / self.total_mutations

    @property
    def precision(self) -> float:
        """Precision over ALL added findings (errors + warnings + info).

        Cascade/dependent findings that legitimately co-fire with the expected
        defect count against this number, so it is the strictest reading.
        """
        if self.total_findings == 0:
            return 0.0
        return self.correct_findings / self.total_findings

    @property
    def error_precision(self) -> float:
        """Precision over ERROR-severity findings only (signoff signal)."""
        if self.total_errors == 0:
            return 0.0
        return self.correct_errors / self.total_errors

    def to_dict(self) -> dict:
        return {
            "total_mutations": self.total_mutations,
            "detected": self.detected,
            "missed": [{"category": c, "name": n, "expected": e}
                       for c, n, e in self.missed],
            "detection_rate": round(self.detection_rate, 4),
            "precision": round(self.precision, 4),
            "error_precision": round(self.error_precision, 4),
            "correct_findings": self.correct_findings,
            "total_findings": self.total_findings,
            "correct_errors": self.correct_errors,
            "total_errors": self.total_errors,
            "baseline_errors": self.baseline_errors,
            "baseline_false_positives": self.baseline_false_positives,
            "per_category": self.per_category,
        }


def _msgset(text: str) -> set:
    res = validate_records(preprocess(text, file="<quality>"))
    return {(f.rule, f.severity, f.message) for f in res.check.findings}


def _added_rules(text: str, base: set) -> set:
    return {r for r, s, m in _msgset(text) - base}


def _added_findings(text: str, base: set) -> set:
    return _msgset(text) - base


def run_quality_report() -> QualityReport:
    """Run the full corpus and compute detection rate + precision."""
    report = QualityReport(total_mutations=len(MUTATIONS))
    base_msgs = _msgset(BASE)

    baseline_res = validate_records(preprocess(BASE, file="<quality>"))
    # Any error on the clean baseline is by definition a false positive:
    # the corpus contract is that valid intent produces zero errors.
    report.baseline_errors = baseline_res.check.error_count
    report.baseline_false_positives = baseline_res.check.error_count

    for cat, name, mutated, expected in MUTATIONS:
        added = _added_findings(mutated, base_msgs)
        added_errors = {(r, s, m) for r, s, m in added if s == "error"}
        expected_hit = any(r == expected for r, s, m in added)
        if expected_hit:
            report.detected += 1
        else:
            report.missed.append((cat, name, expected))
        report.correct_findings += sum(
            1 for r, s, m in added if r == expected)
        report.total_findings += len(added)
        report.correct_errors += sum(
            1 for r, s, m in added_errors if r == expected)
        report.total_errors += len(added_errors)

        per_cat = report.per_category.setdefault(
            cat, {"total": 0, "detected": 0, "missed": []})
        per_cat["total"] += 1
        if expected_hit:
            per_cat["detected"] += 1
        else:
            per_cat["missed"].append(name)

    return report


def format_quality_report(report: QualityReport) -> str:
    """Human-readable quality report for the CLI."""
    lines = [
        "UPF validation quality",
        f"  corpus             : {report.total_mutations} mutations"
        f" ({len(CATEGORIES)} categories)",
        f"  detection rate     : {report.detected}/{report.total_mutations}"
        f" ({report.detection_rate:.0%})",
        f"  precision (errors) : {report.correct_errors}/"
        f"{report.total_errors} error findings correct"
        f" ({report.error_precision:.1%})",
        f"  precision (all)    : {report.correct_findings}/"
        f"{report.total_findings} findings correct"
        f" ({report.precision:.1%})",
        f"  baseline errors    : {report.baseline_errors}",
        f"  baseline false pos : {report.baseline_false_positives}",
    ]
    if report.missed:
        lines.append(f"  MISSED ({len(report.missed)}):")
        for cat, name, expected in report.missed:
            lines.append(f"    - [{cat}] {name}: expected {expected}")
    lines.append("  per category:")
    for cat in CATEGORIES:
        pc = report.per_category.get(cat, {"total": 0, "detected": 0})
        tag = "OK " if pc["detected"] == pc["total"] else "!! "
        lines.append(f"    {tag}{cat:20} {pc['detected']}/{pc['total']}")
    return "\n".join(lines)


__all__ = [
    "BASE", "MUTATIONS", "CATEGORIES", "clean_baseline",
    "QualityReport", "run_quality_report", "format_quality_report",
]
