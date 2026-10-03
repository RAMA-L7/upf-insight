#!/usr/bin/env python
"""Adjudication dataset for UPF-Insight findings on real-world UPF.

The external-corpus work established that the *grammar* layer no longer
invents findings (1.4% grammar-layer FP on AnyCore). That says nothing about
whether the surviving findings are correct. This script builds the dataset
needed to answer that question honestly.

For every finding it records:

* rule id, severity, source file, source line
* the **exact source construct** (the verbatim UPF line/command record)
* the **normalized** representation the rule actually compared
* scope, referenced domains, supply sets/nets/ports
* referenced design objects, when a netlist is supplied
* the full finding message and rule-registry metadata

Findings are then clustered by rule, normalized message shape, source command,
and structural argument pattern, so volume can be attributed to causes rather
than counted as independent evidence.

This script **only observes**. It never edits a rule, and adjudication
verdicts live in ``VERDICTS`` below — each one carrying the reason it was
reached, so a reviewer can disagree with a verdict without re-deriving the
data. Findings whose class cannot be settled from the evidence available get
``UNRESOLVED``; they are never folded into true or false.

Usage:
    python scripts/adjudicate.py                      # both corpora
    python scripts/adjudicate.py --corpus anycore    # one corpus
    python scripts/adjudicate.py -o inventory.json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from upf_insight.engine.engine import validate            # noqa: E402
from upf_insight.engine.rules.rules_registry import (     # noqa: E402
    RULES, RULE_META,
)

# ---------------------------------------------------------------------------
# Corpora (same roots as validate_external.py; kept separate so this script has
# no import-order coupling with the CLI harness).
# ---------------------------------------------------------------------------

CORPORA = {
    "anycore": {
        "root": r"D:\upf-bench\anycore-riscv-src",
        "glob": "power_spec/*.upf",
    },
    "tenstorrent": {
        "root": r"D:\upf-bench\tt",
        "glob": "*.upf",
    },
}

# ---------------------------------------------------------------------------
# Validation classes (Step 6). Every adjudicated finding gets exactly one.
# ---------------------------------------------------------------------------

TRUE_POSITIVE = "TRUE_POSITIVE"            # real semantic violation
VALID_ADVISORY = "VALID_ADVISORY"          # not a violation; intentional caution
FALSE_POSITIVE = "FALSE_POSITIVE"          # finding is simply wrong
UNSUPPORTED_CONSTRUCT = "UNSUPPORTED_CONSTRUCT"   # legal UPF the rule cannot judge
IMPLEMENTATION_DEFECT = "IMPLEMENTATION_DEFECT"   # rule is wrong (code bug)
DUPLICATE_OR_CASCADE = "DUPLICATE_OR_CASCADE"     # downstream of one root cause
UNRESOLVED = "UNRESOLVED"                  # evidence insufficient — stays here

CLASSES = (TRUE_POSITIVE, VALID_ADVISORY, FALSE_POSITIVE, UNSUPPORTED_CONSTRUCT,
           IMPLEMENTATION_DEFECT, DUPLICATE_OR_CASCADE, UNRESOLVED)


def _rule_meta() -> Dict[str, dict]:
    """rule id -> registry metadata (severity, title, description, support)."""
    out: Dict[str, dict] = {}
    for r in RULES:  # type: ignore[name-defined]
        out[r.code] = {
            "title": r.title,
            "layer": r.layer,
            "declared_severity": r.severity,
            "description": r.description,
            "support": RULE_META.get(r.code, {}).get("context"),
            "semantic_inputs": list(RULE_META.get(r.code, {})
                                    .get("semantic_inputs", ())),
            "test_ref": RULE_META.get(r.code, {}).get("test_ref"),
        }
    return out


# ---------------------------------------------------------------------------
# Source provenance
# ---------------------------------------------------------------------------

def _load_records(paths: List[str]):
    from upf_insight.preprocess.upf_preprocess import preprocess_many
    return preprocess_many(paths)


def _record_index(records):
    """(file, line) -> verbatim command text, for provenance."""
    idx = {}
    for rec in records:
        idx.setdefault((str(rec.file), rec.line), rec.text)
    return idx


def _line_of(path: Path, line: Optional[int]) -> Optional[str]:
    """The verbatim physical source line, when readable."""
    if not line:
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if 1 <= line <= len(lines):
            return lines[line - 1]
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Normalization / clustering
# ---------------------------------------------------------------------------

_NUM = re.compile(r"\d+")
_HEX = re.compile(r"0x[0-9a-fA-F]+")


def normalize_message(msg: str) -> str:
    """Collapse a message to its shape so repeats cluster together."""
    s = _HEX.sub("0xN", msg)
    s = re.sub(r"'[^']*'", "'X'", s)          # quoted identifiers
    s = re.sub(r"\b\d+\.\d+\b", "N.N", s)      # floats
    s = _NUM.sub("N", s)                      # remaining integers
    return s


_ARG = re.compile(r"(-[A-Za-z_][\w]*)")


def structural_pattern(record_text: str) -> str:
    """Command plus its option names, values abstracted.

    Groups findings that arise from the same *shape* of UPF construct, so two
    findings with different object names but identical structure cluster.
    """
    if not record_text:
        return ""
    parts = record_text.split()
    if not parts:
        return ""
    cmd = parts[0]
    opts = []
    for p in parts[1:]:
        if _ARG.fullmatch(p):
            opts.append(p)
    return cmd + (" " + ",".join(opts) if opts else "")


def _command_of(record_text: str) -> str:
    return record_text.split()[0] if record_text else ""


# ---------------------------------------------------------------------------
# Per-finding inventory
# ---------------------------------------------------------------------------

def _referenced_objects(model, finding) -> dict:
    """Domains / supplies / design objects named in the message or bound to it."""
    domains, supplies, design_objs = set(), set(), set()
    msg = finding.message
    for name in getattr(model, "domains", {}):
        if name in msg:
            domains.add(name)
    for table in ("supply_sets", "supply_nets", "supply_ports"):
        for key in getattr(model, table, {}):
            leaf = key.split("/")[-1]
            if key in msg or leaf in msg:
                supplies.add(key)
    design = getattr(model, "design", None)
    if design is not None:
        for token in re.findall(r"[A-Za-z_][\w\.\[\]]*", msg):
            try:
                if design.has_signal(token):
                    design_objs.add(token)
            except Exception:
                pass
    return {
        "domains": sorted(domains),
        "supplies": sorted(supplies),
        "design_objects": sorted(design_objs),
    }


def build_inventory(corpus: str, netlist: Optional[str] = None,
                    load_set: bool = True) -> dict:
    """Build the finding inventory for one corpus.

    ``load_set=True`` (default) validates every file together in load order,
    which is how hierarchical UPF is actually consumed — a top file
    ``load_upf``s children into named scopes. ``load_set=False`` validates each
    file alone. The two modes produce different models and therefore different
    finding counts; both are reportable and the mode is recorded in the output.
    """
    spec = CORPORA[corpus]
    root = Path(spec["root"])
    if not root.is_dir():
        return {"corpus": corpus, "available": False,
                "reason": "root %s missing" % root}
    files = sorted(str(p) for p in root.glob(spec["glob"]))
    if not files:
        return {"corpus": corpus, "available": False,
                "reason": "no files matched %s" % spec["glob"]}

    mode = "load-set" if load_set else "per-file"
    if load_set:
        records = _load_records(files)
        rec_idx = _record_index(records)
        results = [validate(files, netlist=netlist)]
    else:
        results = [validate([f], netlist=netlist) for f in files]
        records = []
        rec_idx = _record_index(records)
    result = results[0]
    model = result.check.model
    meta = _rule_meta()

    rows: List[dict] = []
    for res in results:
        mdl = res.check.model
        for f in res.check.findings:
            fpath = f.file or ""
            src = _line_of(Path(fpath), f.line) if fpath else None
            record_text = rec_idx.get((fpath, f.line))
            if record_text is None and fpath:
                # Fall back to any file carrying a record at this line.
                for (rp, rl) in rec_idx:
                    if rl == f.line:
                        record_text = rec_idx[(rp, rl)]
                        break
            row = {
                "rule": f.rule,
                "severity": getattr(f, "severity", None),
                "file": fpath or None,
                "line": f.line,
                "source_construct": src,
                "command_record": record_text,
                "command": _command_of(record_text or ""),
                "structural_pattern": structural_pattern(record_text or ""),
                "message": f.message,
                "normalized_message": normalize_message(f.message),
                "scope": getattr(mdl, "current_scope", None),
                "support": getattr(f, "support", None),
                "stage": f.stage,
                "evidence": list(getattr(f, "evidence", []) or []),
                "subject": getattr(f, "subject", None),
                "blocked_by": getattr(f, "blocked_by", ""),
                "rule_meta": meta.get(f.rule, {}),
            }
            row.update(_referenced_objects(mdl, f))
            rows.append(row)

    return {"corpus": corpus, "available": True, "files": len(files),
            "mode": mode, "findings": rows}


def _infer_file(files: List[str], rec_idx, line) -> Optional[str]:
    """Deprecated: findings carry their own file, so no inference is needed."""
    return files[0] if files else None


# ---------------------------------------------------------------------------
# Clustering (Step 2)
# ---------------------------------------------------------------------------

def cluster(inv: dict) -> dict:
    rows = inv["findings"]
    by_rule = Counter(r["rule"] for r in rows)
    clusters: Dict[str, dict] = defaultdict(lambda: {
        "count": 0, "normalized_messages": Counter(),
        "commands": Counter(), "patterns": Counter(), "files": set(),
        "examples": [],
    })
    for r in rows:
        c = clusters[r["rule"]]
        c["count"] += 1
        c["normalized_messages"][r["normalized_message"]] += 1
        c["commands"][r["command"] or "(none)"] += 1
        c["patterns"][r["structural_pattern"] or "(none)"] += 1
        c["files"].add(r["file"])
        if len(c["examples"]) < 3:
            c["examples"].append(r)
    out = {}
    for rule, c in clusters.items():
        out[rule] = {
            "count": c["count"],
            "distinct_messages": len(c["normalized_messages"]),
            "files": len(c["files"]),
            "messages": c["normalized_messages"].most_common(6),
            "commands": c["commands"].most_common(6),
            "patterns": c["patterns"].most_common(6),
            "examples": c["examples"],
        }
    return {"by_rule_count": by_rule.most_common(), "clusters": out}


# ---------------------------------------------------------------------------
# Verdicts (Step 6/7). Keyed by rule code.
#
# Each verdict carries the *reason* and the *evidence* it rests on, so a
# reviewer can disagree with a conclusion without re-deriving the dataset. A
# rule absent from this table is UNRESOLVED by construction — it is never
# silently counted as correct.
# ---------------------------------------------------------------------------

VERDICTS: Dict[str, dict] = {
    "UPF-087": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": (
            "Every UPF-087 finding on the corpus is a Verilog/UPF *bus bit "
            "select* (e.g. `INST_LOOP[0].ram_instance`, "
            "`SW_x/vout`, `alPartitionActive_i[2]`), not a wildcard. "
            "WILDCARD_CHARS includes '[', so any bracketed index is scored as "
            "a glob. 309/309 corpus findings carry a numeric index; 0/309 "
            "contain a real `*`/`?` or a character-class pattern such as "
            "[abc]. In IEEE 1801 an element list names design objects; "
            "`inst[3]` selects one array element exactly and has no pattern "
            "semantics. The project's own netlist parser agrees: it expands "
            "`data_in[0]` into literal per-bit signals rather than a pattern. "
            "The rule contradicts the rest of the codebase."),
        "evidence": ("source-level: grep of all 309 flagged patterns; "
                     "internal consistency: netlist_parser bus expansion; "
                     "no test covered a bit-select"),
    },
    "UPF-025": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": (
            "Reported as cascades of the add_pst_state parsing defect (see "
            "add_pst_state). The supply states ARE referenced — "
            "ActiveList.upf declares `-state {ACTIVE ACTIVE OFF OFF}` "
            "against `create_pst ... -supplies {VDD VSS sw2/vout sw3/vout}`. "
            "Because those entries were mis-parsed, the reference lookup "
            "misses and every state reads as unreferenced."),
        "evidence": ("cascade: UPF-031 reports \"state 'ACTIVE' on supply "
                     "'ACTIVE'\", exposing the mis-pairing directly"),
    },
    "UPF-030": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": "Same add_pst_state parsing root cause as UPF-025.",
        "evidence": "cascade of add_pst_state",
    },
    "UPF-031": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": (
            "Directly exposes the add_pst_state parsing defect: reports "
            "\"uses undeclared state 'ACTIVE' on supply 'ACTIVE'\". IEEE 1801 "
            "maps `-state` entries POSITIONALLY onto `create_pst -supplies`; "
            "the builder instead reads them as consecutive (name, value) "
            "pairs, so a state name is used as its own supply name."),
        "evidence": ("IEEE 1801 positional correspondence; self-referential "
                     "message 'on supply ACTIVE' is not expressible in valid "
                     "UPF"),
    },
    "UPF-034": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": "Downstream of the add_pst_state parsing defect.",
        "evidence": "cascade of add_pst_state",
    },
    "UPF-038": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": (
            "Split verdict. 220 findings at v1.4a, of which ~140 were an "
            "IMPLEMENTATION_DEFECT now fixed: `create_pst -supplies` may name "
            "a switched supply either by its net (VDD_SW) or by the switch's "
            "output PORT path (SW_CORE/vout) — both legal, and AnyCore uses "
            "both (23 such columns). The PST compared only against net names, "
            "so every port-named supply read as unmodeled. Fixed by retaining "
            "the port roles in the IR (output_port_role/input_port_role) and "
            "resolving a switch output under all its legal names. 220 -> 80. "
            "The residual 80 are DUPLICATE_OR_CASCADE, not rule errors: nine "
            "files each declare a PST named Core_OOO_PST with a *different* "
            "supply list, and load-set mode keys PSTs by scope only, so the "
            "last one silently overwrites the rest. FABSCALAR.upf's 11-column "
            "PST is replaced by a 5-column one, whose columns of course do "
            "not model those supplies."),
        "evidence": ("source: ActiveList.upf:63 vs FABSCALAR.upf:230; "
                     "PST collision counted across 9 files"),
    },
    "UPF-010": {
        "class": IMPLEMENTATION_DEFECT,
        "reason": (
            "Mixed. 72 of 148 name a switch output PORT path (SW_x/vout) that "
            "the model already knows about — the reference is legal IEEE 1801 "
            "and the supply lookup does not resolve switch ports, the same gap "
            "fixed in UPF-038. The other 76 are scoped references "
            "(counter_gen[0].counterTable/VDD) whose defining file may be "
            "outside the load set; those are held UNRESOLVED rather than "
            "guessed."),
        "evidence": "72/148 subjects are known switch port paths",
    },
    "UPF-016": {
        "class": VALID_ADVISORY,
        "reason": (
            "141 findings, all the same message: `set_scope` targets cannot be "
            "verified without a netlist. The rule asserts no defect — it "
            "reports its own support boundary (support=NETLIST_REQUIRED) and "
            "the checker downgrades it from error to warning. This is the "
            "intended honest-boundary behaviour, not a finding about the UPF."),
        "evidence": "message is a self-declared NETLIST_REQUIRED boundary",
    },
    "UPF-097": {
        "class": VALID_ADVISORY,
        "reason": (
            "75 findings, same shape as UPF-016: hierarchical UPF composed via "
            "load_upf cannot be cross-resolved without a netlist. Reports a "
            "boundary, not a defect in the design."),
        "evidence": "message is a self-declared NETLIST_REQUIRED boundary",
    },
    "UPF-013": {
        "class": DUPLICATE_OR_CASCADE,
        "reason": (
            "238 findings, all with subject 'TOP', from 4 files. The corpus "
            "re-enters shared files into child scopes (`load_upf BTB.upf` "
            "under /fs1, /btb, ...), which legitimately redefines names in a "
            "different scope. The duplicate detector does not scope-qualify, "
            "so one root condition floods 238 findings — 216 of which carry "
            "no file attribution at all. Not 238 independent defects."),
        "evidence": ("cluster: single subject, 4 files, 216 findings with "
                     "empty file field"),
    },
}


def summarize(inv: dict, cl: dict) -> dict:
    rows = inv["findings"]
    tally: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        v = VERDICTS.get(r["rule"], {}).get("class", UNRESOLVED)
        tally[r["rule"]][v] += 1
    per_rule = {}
    for rule, total in cl["by_rule_count"]:
        cnt = tally.get(rule, Counter())
        per_rule[rule] = {
            "total": total,
            **{k: cnt.get(k, 0) for k in CLASSES},
            "verdict_reason": VERDICTS.get(rule, {}).get("reason"),
            "evidence": VERDICTS.get(rule, {}).get("evidence"),
        }
    return {
        "corpus": inv["corpus"],
        "files": inv.get("files"),
        "total_findings": len(rows),
        "per_rule": per_rule,
    }


# ---------------------------------------------------------------------------

def quality_metrics(inv: dict, cl: dict) -> dict:
    """The metrics panel from the roadmap, replacing a single FP number.

    A single false-positive rate hides more than it shows: it conflates "could
    not read the file" with "read it and disagreed", and it silently treats
    unadjudicated findings as either correct or incorrect. These metrics keep
    the distinctions visible.
    """
    rows = inv["findings"]
    total = len(rows)
    by_rule = dict(cl["by_rule_count"])

    adjudicated = Counter()
    for rule, n in by_rule.items():
        v = VERDICTS.get(rule)
        if v:
            adjudicated[v["class"]] += n
    adjudicated_total = sum(adjudicated.values())

    stages = Counter()
    for r in rows:
        stages[r.get("stage") or "SEMANTIC"] += 1

    # Cascade / duplicate signal: many findings sharing one subject, or many
    # findings on one rule sharing a normalized message and no file.
    by_subject = Counter(r.get("subject") or "(none)" for r in rows)
    cascade_findings = sum(n for s, n in by_subject.items()
                           if s != "(none)" and n > 1)

    grammar_fp = sum(n for rule, n in by_rule.items()
                     if rule in ("UPF-001", "UPF-002", "UPF-003", "UPF-024"))

    unresolved = adjudicated.get(UNRESOLVED, 0) + (total - adjudicated_total)

    return {
        "files_processed": inv.get("files"),
        "mode": inv.get("mode"),
        "total_findings": total,
        "parse_stage_findings": stages.get("PARSE", 0),
        "grammar_layer_fp": grammar_fp,
        "grammar_fp_rate": round(grammar_fp / total * 100, 1) if total else 0.0,
        "stages": dict(stages),
        "adjudicated": adjudicated_total,
        "adjudicated_pct": round(adjudicated_total / total * 100, 1) if total else 0.0,
        "by_class": dict(adjudicated),
        "unresolved": unresolved,
        "unresolved_pct": round(unresolved / total * 100, 1) if total else 0.0,
        "distinct_rules": len(by_rule),
        "cascade_findings": cascade_findings,
        "cascade_pct": round(cascade_findings / total * 100, 1) if total else 0.0,
        "findings_with_provenance": sum(1 for r in rows if r.get("file")),
        "provenance_pct": (
            round(sum(1 for r in rows if r.get("file")) / total * 100, 1)
            if total else 0.0),
    }


def print_metrics(m: dict) -> None:
    print("\n-- quality metrics --")
    rows = [
        ("Files processed", m["files_processed"]),
        ("Mode", m["mode"]),
        ("Total findings", m["total_findings"]),
        ("Parse-stage findings", m["parse_stage_findings"]),
        ("Grammar-layer FP", "%d (%.1f%%)" % (m["grammar_layer_fp"],
                                              m["grammar_fp_rate"])),
        ("Adjudicated", "%d (%.1f%%)" % (m["adjudicated"], m["adjudicated_pct"])),
        ("Unresolved", "%d (%.1f%%)" % (m["unresolved"], m["unresolved_pct"])),
        ("Cascade/duplicate", "%d (%.1f%%)" % (m["cascade_findings"],
                                               m["cascade_pct"])),
        ("With file provenance", "%.1f%%" % m["provenance_pct"]),
        ("Stage split", m["stages"]),
    ]
    for label, value in rows:
        print("  %-22s %s" % (label, value))
    if m["by_class"]:
        print("  Adjudicated classes:")
        for k, v in sorted(m["by_class"].items(), key=lambda kv: -kv[1]):
            print("     %5d  %s" % (v, k))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="all", choices=[*CORPORA, "all"])
    ap.add_argument("--netlist", help="optional netlist JSON for design objects")
    ap.add_argument("-o", "--out", help="write the dataset JSON here")
    ap.add_argument("--per-file", action="store_true",
                    help="validate each file alone instead of as one load set")
    args = ap.parse_args()

    names = list(CORPORA) if args.corpus == "all" else [args.corpus]
    data = {}
    for name in names:
        inv = build_inventory(name, args.netlist,
                              load_set=not args.per_file)
        if not inv["available"]:
            data[name] = inv
            continue
        cl = cluster(inv)
        data[name] = {"inventory": inv, "clusters": cl,
                      "summary": summarize(inv, cl),
                      "metrics": quality_metrics(inv, cl)}
    if args.out:
        Path(args.out).write_text(json.dumps(data, indent=2, default=str),
                                  encoding="utf-8")

    for name, d in data.items():
        if not d.get("available", True) and "summary" not in d:
            print("== %s UNAVAILABLE: %s" % (name, d.get("reason")))
            continue
        s = d["summary"]
        print("\n== %s: %d findings across %d files (%s)"
              % (name, s["total_findings"], s["files"], d["metrics"]["mode"]))
        print_metrics(d["metrics"])
        print("\n%-10s %7s  %s" % ("RULE", "COUNT", "VERDICT"))
        for rule, n in d["clusters"]["by_rule_count"]:
            v = VERDICTS.get(rule, {}).get("class", UNRESOLVED)
            print("%-10s %7d  %s" % (rule, n, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())