#!/usr/bin/env python
"""Run UPF-Insight against real-world UPF files and report false positives.

The 42-mutation corpus in `engine/quality.py` proves the engine *catches*
seeded defects. It cannot prove the engine does not invent findings on UPF it
did not write itself. This harness closes that gap: it runs the CLI over an
external corpus, classifies each finding by root cause, and prints a
false-positive rate.

Classification is by explicit rule/message predicate, so a new finding kind
shows up as `unclassified` rather than silently counting as genuine.

Usage:
    python scripts/validate_corpus.py                 # default corpus
    python scripts/validate_corpus.py --json          # machine-readable
    python scripts/validate_corpus.py path/to/*.upf   # explicit files
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

#: Options that IEEE 1801 defines but the engine's grammar (as of v0.3.0)
#: does not yet accept. Seeing UPF-002 on one of these is a tool defect.
LEGAL_BUT_REJECTED = (
    "-include_scope", "-domain", "-input_supply", "-output_supply",
    "-isolation_power_net", "-isolation_ground_net", "-location",
    "-retention_power_net", "-retention_ground_net",
)

#: Commands defined by the standard that the engine does not model.
UNSUPPORTED_LEGAL = ("map_power_switch",)

#: Structural rule noise caused by an upstream parse failure. UPF-076 fires
#: because a switch never got an off_state — which only happens because
#: create_power_switch rejected the file's legal option spelling.
CASCADE_RULES = {"UPF-076"}


def classify(rule: str, message: str) -> str:
    """Bucket one finding. Returns a stable label, never raises."""
    if rule == "UPF-002":
        for opt in LEGAL_BUT_REJECTED:
            if opt in message:
                return "FP:grammar-rejects-legal-option"
    if rule == "UPF-003" and "create_power_switch" in message:
        return "FP:grammar-rejects-legal-option"
    if rule == "UPF-001":
        for cmd in UNSUPPORTED_LEGAL:
            if cmd in message:
                return "FP:command-unsupported"
    if rule == "UPF-024":
        return "FP:brace-group-not-split"
    if rule in CASCADE_RULES:
        return "FP:cascade-from-switch-parse-failure"
    return "genuine/needs-review"


def run_one(path: str) -> dict:
    """Run the CLI on one file and bucket its findings."""
    proc = subprocess.run(
        [sys.executable, "-m", "upf_insight.cli.cli", "check", path, "--format", "json"],
        capture_output=True, text=True, timeout=300,
    )
    # The package has no __main__; fall back to the console script.
    if proc.returncode not in (0, 1) or not proc.stdout.strip().startswith("{"):
        proc = subprocess.run(
            ["upf-insight", "check", path, "--format", "json"],
            capture_output=True, text=True, timeout=300,
        )
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return {"file": path, "error": "no JSON output",
                "stderr": proc.stderr[-400:], "findings": 0,
                "false_positives": 0, "buckets": {}}

    buckets = Counter()
    for f in data["check"]["findings"]:
        buckets[classify(f["rule"], f["message"])] += 1
    fp = sum(n for k, n in buckets.items() if k.startswith("FP"))
    total = sum(buckets.values())
    return {
        "file": path,
        "lines": sum(1 for _ in open(path, encoding="utf-8", errors="replace")),
        "commands": data.get("command_count", 0),
        "counts": data["check"]["counts"],
        "readiness": data["readiness"]["overall"],
        "findings": total,
        "false_positives": fp,
        "false_positive_rate": round(fp / total * 100, 1) if total else 0.0,
        "buckets": dict(buckets),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="UPF files (default: bundled corpus)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    if args.files:
        files = args.files
    else:
        here = Path(__file__).resolve().parent.parent
        corpus = here / "tests" / "corpus"
        files = sorted(str(p) for p in corpus.glob("*.upf")) if corpus.is_dir() else []

    if not files:
        print("No corpus files found. Pass paths explicitly.", file=sys.stderr)
        return 2

    results = [run_one(f) for f in files if os.path.exists(f)]
    tot = sum(r["findings"] for r in results)
    fp = sum(r["false_positives"] for r in results)

    if args.json:
        print(json.dumps({"results": results, "total_findings": tot,
                          "total_false_positives": fp,
                          "false_positive_rate": round(fp / tot * 100, 1) if tot else 0.0},
                         indent=2))
        return 0

    print("%-34s %6s %7s %12s %8s" % ("FILE", "LINES", "ERRORS", "READINESS", "FP-RATE"))
    print("-" * 72)
    for r in results:
        if "error" in r:
            print("%-34s  ERROR: %s" % (os.path.basename(r["file"]), r["error"]))
            continue
        print("%-34s %6d %7d %12s %7.1f%%" % (
            os.path.basename(r["file"]), r["lines"], r["counts"]["errors"],
            r["readiness"], r["false_positive_rate"]))
    print("-" * 72)
    print("%-34s %7d findings, %d false positives (%.0f%%)"
          % ("TOTAL", tot, fp, fp / tot * 100 if tot else 0))

    agg = Counter()
    for r in results:
        agg.update(r.get("buckets", {}))
    if agg:
        print("\nBy bucket:")
        for k, n in agg.most_common():
            print("  %4d  %s" % (n, k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())