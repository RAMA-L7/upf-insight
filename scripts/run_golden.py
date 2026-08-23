"""Golden regression runner.

Runs the full engine over every fixture in tests/examples and compares the
result signatures against evidence/manifest/golden_results.json.

A result signature is the deterministic tuple (rule, severity, subject) of
every finding - stable against message rewording but sensitive to any change
in rule behavior, exactly like the rta golden runners.

Usage:
    python scripts/run_golden.py            # compare (creates on first run)
    python scripts/run_golden.py --update   # re-record after intentional change
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from upf_insight.engine.engine import validate  # noqa: E402

RESULTS = ROOT / "evidence" / "manifest" / "golden_results.json"
FIXTURE_ROOTS = [ROOT / "tests" / "examples"]
EXTENSIONS = {".upf", ".tcl"}
IGNORED_DIRS = {"__pycache__", ".pytest_cache"}


def discover_fixtures() -> list[Path]:
    out: list[Path] = []
    for root in FIXTURE_ROOTS:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTENSIONS \
                    and not any(part in IGNORED_DIRS for part in p.parts):
                out.append(p)
    return out


def signature(path: Path) -> dict:
    result = validate([str(path)])
    sigs = [
        {"rule": f.rule, "severity": f.severity,
         "subject": f.subject or ""}
        for f in result.check.findings
    ]
    return {
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "error_count": result.check.error_count,
        "warning_count": result.check.warning_count,
        "readiness": (result.readiness.overall
                      if result.readiness else None),
        "findings": sorted(sigs, key=lambda s: (s["rule"], s["subject"],
                                                s["severity"])),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="re-record golden results")
    args = ap.parse_args()
    fixtures = discover_fixtures()
    if not fixtures:
        print("no fixtures found under tests/examples")
        return 1
    current = [signature(p) for p in fixtures]
    if args.update or not RESULTS.exists():
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(current, indent=2, sort_keys=True) + "\n"
        RESULTS.write_text(payload, encoding="utf-8", newline="\n")
        verb = "recorded" if args.update else "created"
        print(f"{verb} golden results for {len(current)} fixture(s): {RESULTS}")
        return 0
    expected = json.loads(RESULTS.read_text(encoding="utf-8"))
    if expected == current:
        print(f"golden regression clean ({len(current)} fixtures)")
        return 0
    by_file = {e["file"]: e for e in expected}
    for c in current:
        e = by_file.get(c["file"])
        if e is None:
            print(f"GOLDEN DRIFT: new fixture {c['file']}")
            continue
        if e != c:
            old = {(f["rule"], f["subject"]) for f in e["findings"]}
            new = {(f["rule"], f["subject"]) for f in c["findings"]}
            added = sorted(new - old)
            removed = sorted(old - new)
            print(f"GOLDEN DRIFT in {c['file']}:")
            for a in added:
                print(f"  + {a[0]} {a[1]}")
            for r in removed:
                print(f"  - {r[0]} {r[1]}")
    known = set(by_file)
    for c in current:
        known.discard(c["file"])
    for gone in sorted(known):
        print(f"GOLDEN DRIFT: fixture removed: {gone}")
    print("intentional change? re-record with: "
          "python scripts/run_golden.py --update")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
