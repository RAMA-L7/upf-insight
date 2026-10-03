#!/usr/bin/env python
"""Validate UPF-Insight against external, production-style UPF corpora.

`validate_corpus.py` measures the *shipped* corpus, whose grammar-coverage file
this project authored. That cannot prove the parser handles UPF written by
somebody else. This harness closes that gap against real open-source power
intent, and is the procedure referenced by
`docs/validation/REAL_WORLD_REPORT.md` for re-measuring the historical
AnyCore / Tenstorrent numbers.

Design constraints (from the validation charter):

* **Read-only.** External files are never modified. A SHA-256 manifest is
  taken before and after the run and compared, so an accidental write is
  caught rather than assumed absent.
* **Deterministic.** No timestamps, no hash-order dependence, sorted output.
  Two runs must be byte-identical; `--verify-determinism` checks that.
* **No silent reclassification.** Every finding lands in exactly one of five
  categories (parser failure / normalization failure / genuine semantic /
  ambiguous / validator defect). Anything not matched by an explicit predicate
  is reported as `ambiguous/needs-review` with its raw rule and message, so a
  new failure mode surfaces instead of being quietly scored as genuine.

Usage:
    python scripts/validate_external.py --corpus anycore
    python scripts/validate_external.py --corpus tenstorrent
    python scripts/validate_external.py --corpus all --json -o report.json
    python scripts/validate_external.py --corpus anycore --verify-determinism

A corpus that is absent is reported as `unavailable` with the reason, never
skipped silently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

#: Known external corpora. ``root`` is a local checkout; ``repo`` records
#: provenance so a reader can re-acquire the exact revision independently.
CORPORA: Dict[str, dict] = {
    "anycore": {
        "root": r"D:\upf-bench\anycore-riscv-src",
        "glob": "power_spec/*.upf",
        "repo": "https://github.com/anycore/anycore-riscv-src",
        "commit": "419cc6cd1e709018de91b32285e79441c1c8c560",
        "license": "NCSU copyright (see LICENSE)",
        "baseline": {"files": 37, "findings": 4012, "fp_rate": 65.0},
    },
    "tenstorrent": {
        "root": r"D:\upf-bench\tt",
        "glob": "*.upf",
        "repo": "https://github.com/tenstorrent/tt-metal (local copy)",
        "commit": "local snapshot",
        "license": "Apache-2.0 (SPDX header in file)",
        "baseline": {"files": 1, "findings": 1, "fp_rate": 100.0},
    },
}

# --------------------------------------------------------------------------
# Classification vocabulary.
#
# Each predicate returns a category, or None to fall through. Categories are
# prefixed so the FP total is a prefix match on the parser/normalization/
# validator buckets — genuine and ambiguous never count as false positives.
# --------------------------------------------------------------------------

#: Commands the engine models. Anything else reported by UPF-001 is either a
#: genuine unknown command or a standard command we lack.
_MODELLED = {
    "upf_version", "set_design_top", "create_power_domain", "set_scope",
    "load_upf", "create_supply_net", "create_supply_port", "create_supply_set",
    "connect_supply_net", "create_power_switch", "add_port_state",
    "add_supply_state", "add_power_state", "create_pst", "add_pst_state",
    "add_state_transition", "set_isolation", "set_isolation_control",
    "map_isolation_cell", "set_level_shifter", "set_level_shifter_control",
    "map_level_shifter_cell", "set_retention", "set_retention_control",
    "map_retention_cell", "set_repeater", "set_repeater_control",
    "set_domain_supply_net", "set_port_attributes", "set_equivalent",
    "update_supply_net", "update_supply_set", "map_power_switch",
    "upf_promote", "upf_demote",
}

#: A command token that is really a brace/fragment artifact: a stray closer, a
#: bare `{`, or a continuation line. UPF-001 on one of these is the parser
#: splitting a multi-line construct (defect D4).
_FRAGMENT_CMD = re.compile(r"^(\}|\{|\]|\s*)$")

#: An unexpanded Tcl list reaching a semantic rule: '{a b}' compared as one
#: literal name. Defect class D3/D5.
_BRACE_LITERAL = re.compile(r"'\{[^}]*\s[^}]*\}'")

_QUOTED = re.compile(r"'([^']*)'")


def _first_quoted(message: str) -> str:
    m = _QUOTED.search(message)
    return m.group(1) if m else ""


def classify(rule: str, message: str) -> str:
    """Bucket one finding into exactly one category. Never raises."""
    # --- parser failure: the input was split incorrectly -------------------
    if rule == "UPF-001":
        cmd = _first_quoted(message).split(" ")[0]
        if _FRAGMENT_CMD.match(cmd):
            return "parser-failure:brace-fragment-as-command"
        if cmd in _MODELLED:
            return "parser-failure:modelled-command-rejected"
        return "parser-failure:unsupported-command"

    if rule == "UPF-006":
        return "parser-failure:unbalanced-tcl"

    # --- normalization failure: legal UPF, literal reached a rule -----------
    if rule == "UPF-002":
        return "normalization-failure:legal-option-rejected"
    if rule == "UPF-003":
        return "normalization-failure:required-arg-alias-missing"
    if rule == "UPF-024":
        return "normalization-failure:brace-group-not-split"

    # A rule reporting a name that still carries its braces means the pair/list
    # was never split before lookup.
    if _BRACE_LITERAL.search(message):
        return "normalization-failure:brace-literal-reaches-rule"

    # --- cascade: a rule that can only fire because parsing failed ---------
    if rule == "UPF-076":
        return "parser-failure:cascade-switch-unparsed"

    # --- genuinely semantic, or ambiguous ----------------------------------
    if rule.startswith("UPF-0") or rule.startswith("UPF-1"):
        return "ambiguous/needs-review"

    return "ambiguous/needs-review"


def _fp(categories: Counter) -> int:
    """False positives = parser, normalization, and validator buckets."""
    return sum(n for k, n in categories.items()
               if k.startswith(("parser-failure", "normalization-failure",
                                "validator-defect")))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest(files: List[Path]) -> Dict[str, str]:
    return {str(p): sha256(p) for p in files}


def run_one(path: Path) -> dict:
    """Run the CLI over one file and bucket its findings."""
    proc = subprocess.run(
        [sys.executable, "-m", "upf_insight.cli.cli", "check", str(path),
         "--format", "json"],
        capture_output=True, text=True, timeout=300, cwd=str(Path(__file__).resolve().parent.parent),
    )
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return {"file": path.name, "error": "no JSON output",
                "stderr": proc.stderr[-400:], "findings": 0,
                "false_positives": 0, "categories": {}, "blocked": True}

    cats = Counter()
    by_rule = Counter()
    by_severity = Counter()
    for f in data["check"]["findings"]:
        cats[classify(f["rule"], f["message"])] += 1
        by_rule[f["rule"]] += 1
        by_severity[f["severity"]] += 1

    domains = (data.get("model") or {}).get("domains") or {}
    return {
        "file": path.name,
        "lines": sum(1 for _ in open(path, encoding="utf-8", errors="replace")),
        "commands": data.get("command_count", 0),
        "counts": data["check"]["counts"],
        "readiness": data["readiness"]["overall"],
        "findings": sum(cats.values()),
        "false_positives": _fp(cats),
        "by_rule": dict(sorted(by_rule.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "categories": dict(sorted(cats.items())),
        "domains_parsed": len(domains),
        "elements_total": sum(len(d.get("elements") or []) for d in domains.values()),
        "domain_names": sorted(domains),
        "blocked": False,
    }


def collect(name: str) -> tuple:
    """Return (files, provenance-or-reason). Read-only."""
    spec = CORPORA[name]
    root = Path(spec["root"])
    if not root.is_dir():
        return [], ("corpus root %s does not exist on this host" % root)
    files = sorted(root.glob(spec["glob"]))
    if not files:
        return [], ("no files matched %s under %s" % (spec["glob"], root))
    return files, spec


def run_load_set(files: List[Path]) -> dict:
    """Validate the whole corpus as ONE load set, in filename order.

    Hierarchical UPF is not a set of independent files: a top file ``load_upf``s
    children into named scopes, and a supply declared in a child is referenced
    by the parent. Validating each file alone therefore under-reports the model
    and manufactures cross-file "unknown target" findings that do not exist in
    the real flow. This runs the realistic configuration.
    """
    here = Path(__file__).resolve().parent.parent
    code = (
        "import sys,json,collections\n"
        "sys.path.insert(0, %r)\n"
        "from upf_insight.engine.engine import validate\n"
        "r = validate(%r)\n"
        "cats = collections.Counter()\n"
        "by_rule = collections.Counter(); by_sev = collections.Counter()\n"
        "sys.path.insert(0, %r)\n"
        "from scripts.validate_external import classify\n"
        "for f in r.check.findings:\n"
        "    cats[classify(f.rule, f.message)] += 1\n"
        "    by_rule[f.rule] += 1; by_sev[f.severity] += 1\n"
        "m = r.check.model\n"
        "print(json.dumps({\n"
        "  'findings': sum(cats.values()),\n"
        "  'categories': dict(cats), 'by_rule': dict(by_rule),\n"
        "  'by_severity': dict(by_sev),\n"
        "  'domains': len(m.domains), 'nets': len(m.supply_nets),\n"
        "  'elements': sum(len(d.elements) for d in m.domains.values()),\n"
        "  'unsupported_commands': len(m.unsupported_commands),\n"
        "}))\n"
    ) % (str(here), [str(f) for f in files], str(here))
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, timeout=900)
    try:
        d = json.loads(proc.stdout)
    except ValueError:
        return {"error": "load-set run produced no JSON", "stderr": proc.stderr[-400:]}
    d["false_positives"] = _fp(Counter(d["categories"]))
    d["false_positive_rate"] = (
        round(d["false_positives"] / d["findings"] * 100, 1) if d["findings"] else 0.0)
    return d


def run_corpus(name: str, verify_determinism: bool = False,
               load_set: bool = False) -> dict:
    files, prov = collect(name)
    if not files:
        return {"corpus": name, "available": False, "reason": prov}

    before = manifest(files)
    results = [run_one(f) for f in files]
    after = manifest(files)
    integrity = {
        "unmodified": before == after,
        "files_hashed": len(before),
        "digest_of_digests": hashlib.sha256(
            "".join(f"{k}:{v}" for k, v in sorted(before.items())).encode()
        ).hexdigest(),
    }

    cats: Counter = Counter()
    by_rule: Counter = Counter()
    by_sev: Counter = Counter()
    tot = fp = blocked = 0
    for r in results:
        cats.update(r.get("categories", {}))
        by_rule.update(r.get("by_rule", {}))
        by_sev.update(r.get("by_severity", {}))
        tot += r["findings"]
        fp += r["false_positives"]
        blocked += 1 if r.get("blocked") else 0

    out = {
        "corpus": name,
        "available": True,
        "provenance": {k: prov[k] for k in ("repo", "commit", "license")},
        "baseline": prov["baseline"],
        "files": len(files),
        "mode": "per-file" + (" +load-set" if load_set else ""),
        "total_findings": tot,
        "false_positives": fp,
        "false_positive_rate": round(fp / tot * 100, 1) if tot else 0.0,
        "blocked_files": blocked,
        "by_rule": dict(sorted(by_rule.items())),
        "by_severity": dict(sorted(by_sev.items())),
        "categories": dict(sorted(cats.items())),
        "semantic_findings": sum(
            n for k, n in cats.items()
            if not k.startswith(("parser-failure", "normalization-failure"))
        ),
        "domains_parsed": sum(r.get("domains_parsed", 0) for r in results),
        "elements_total": sum(r.get("elements_total", 0) for r in results),
        "source_integrity": integrity,
        "per_file": results,
    }
    if load_set:
        out["as_load_set"] = run_load_set(files)

    if verify_determinism:
        second = [run_one(f) for f in files]
        a = json.dumps([{k: v for k, v in r.items() if k != "file"} for r in results],
                       sort_keys=True)
        b = json.dumps([{k: v for k, v in r.items() if k != "file"} for r in second],
                       sort_keys=True)
        out["determinism"] = {"identical": a == b,
                              "method": "two full passes, per-file results compared"}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="all",
                    choices=[*CORPORA, "all"])
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("-o", "--out", help="write JSON to this path")
    ap.add_argument("--verify-determinism", action="store_true",
                    help="run every file twice and compare")
    ap.add_argument("--load-set", action="store_true",
                    help="also validate the whole corpus as one load set "
                         "(the realistic hierarchical flow)")
    args = ap.parse_args()

    names = list(CORPORA) if args.corpus == "all" else [args.corpus]
    report = {"corpora": [run_corpus(n, args.verify_determinism, args.load_set)
                          for n in names]}

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True),
                                  encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    for c in report["corpora"]:
        if not c["available"]:
            print("\n== %s: UNAVAILABLE — %s" % (c["corpus"], c["reason"]))
            continue
        b = c["baseline"]
        print("\n== %s  (%d files, %s)" % (c["corpus"], c["files"],
                                            c["provenance"]["repo"]))
        print("   baseline: %d files, %d findings, %.0f%% FP"
              % (b["files"], b["findings"], b["fp_rate"]))
        print("   measured: %d findings, %d FP (%.1f%%), %d blocked, "
              "%d domains, %d elements"
              % (c["total_findings"], c["false_positives"],
                 c["false_positive_rate"], c["blocked_files"],
                 c["domains_parsed"], c["elements_total"]))
        print("   source unmodified: %s (%d files hashed)"
              % (c["source_integrity"]["unmodified"],
                 c["source_integrity"]["files_hashed"]))
        print("   by severity: %s" % c["by_severity"])
        print("   categories:")
        for k, n in sorted(c["categories"].items(), key=lambda kv: -kv[1]):
            print("     %5d  %s" % (n, k))
        print("   by rule:")
        for k, n in sorted(c["by_rule"].items(), key=lambda kv: -kv[1]):
            print("     %5d  %s" % (n, k))
        if "determinism" in c:
            print("   deterministic across two runs: %s"
                  % c["determinism"]["identical"])
        ls = c.get("as_load_set")
        if ls and "error" not in ls:
            print("   -- as one load set (realistic hierarchical flow) --")
            print("   measured: %d findings, %d FP (%.1f%%), %d domains, "
                  "%d nets, %d elements"
                  % (ls["findings"], ls["false_positives"],
                     ls["false_positive_rate"], ls["domains"], ls["nets"],
                     ls["elements"]))
            print("   categories: %s" % ls["categories"])
        elif ls:
            print("   load-set run failed: %s" % ls["error"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())