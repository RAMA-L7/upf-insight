"""Build the machine-checked release evidence manifest.

Mirrors the rta evidence-as-product pattern: canonical product facts are
computed live from the installed package and written to
evidence/manifest/RELEASE_EVIDENCE.json. CI can re-run this script and
require an unchanged file, so the manifest cannot drift from the code.

Usage:
    python scripts/build_evidence.py            # write the manifest
    python scripts/build_evidence.py --verify   # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from upf_insight import __version__  # noqa: E402
from upf_insight.engine.rules.rules_registry import registered_rules  # noqa: E402
from upf_insight.model.builder import _LEGAL_OPTIONS, _SUPPORTED  # noqa: E402

MANIFEST = ROOT / "evidence" / "manifest" / "RELEASE_EVIDENCE.json"


def build_evidence() -> dict:
    rules = registered_rules()
    by_layer: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_context: dict[str, int] = {}
    for r in rules:
        by_layer[r.layer] = by_layer.get(r.layer, 0) + 1
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        by_context[r.context] = by_context.get(r.context, 0) + 1
    return {
        "product": "upf-insight",
        "version": __version__,
        "release_status": "deterministic-engine",
        "license": "MIT",
        "python": platform.python_version(),
        "rule_count": len(rules),
        "rules_by_layer": dict(sorted(by_layer.items())),
        "rules_by_severity": dict(sorted(by_severity.items())),
        "rules_by_context": dict(sorted(by_context.items())),
        "supported_commands": sorted(_SUPPORTED),
        "supported_command_count": len(_SUPPORTED),
        "commands_with_option_schema": sorted(_LEGAL_OPTIONS),
        "engine": {
            "llm_in_analysis_path": False,
            "deterministic": True,
            "evidence_traced_to_line": True,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true",
                    help="check the manifest matches the live computation")
    args = ap.parse_args()
    evidence = build_evidence()
    text = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.verify:
        if not MANIFEST.exists():
            print(f"evidence manifest missing: {MANIFEST}")
            return 1
        current = MANIFEST.read_text(encoding="utf-8")
        if current != text:
            print("evidence manifest is stale; run: "
                  "python scripts/build_evidence.py")
            return 1
        print(f"evidence manifest verified: {MANIFEST}")
        return 0
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {MANIFEST} ({evidence['rule_count']} rules, "
          f"{evidence['supported_command_count']} commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
