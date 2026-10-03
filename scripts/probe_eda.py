#!/usr/bin/env python
"""Probe the local EDA environment and record exact, reproducible versions.

An earlier validation report stated "no EDA tools installed". That was wrong:
it checked only `PATH`. The OSS CAD Suite bundle lives at
`D:/tools/oss-cad-suite/` and is not on `PATH` by default — its `bin/` and
`lib/` directories must be prepended, or the binaries fail to load their DLLs
(`libreadline8.dll` etc.).

This script probes properly and writes a record that can be committed, so the
next person does not repeat the mistake.

Usage:
    python scripts/probe_eda.py            # human-readable table
    python scripts/probe_eda.py --json     # machine-readable
    python scripts/probe_eda.py --write    # write docs/validation/EDA_ENVIRONMENT.md
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

#: Where the OSS CAD Suite (YosysHQ) is installed on this host.
SUITE = Path(r"D:\tools\oss-cad-suite")

#: Tool -> (bundle-relative exe, version args). None means "run bare".
TOOLS = [
    ("Yosys",            "yosys.exe",        ["-V"]),
    ("Icarus Verilog",   "iverilog.exe",     ["-V"]),
    ("Icarus runtime",   "vvp.exe",          ["-V"]),
    ("Verilator",        "verilator_bin.exe", ["--version"]),
    ("nextpnr-ecp5",     "nextpnr-ecp5.exe", ["--version"]),
    ("nextpnr-generic",  "nextpnr-generic.exe", ["--version"]),
    ("SymbiYosys",       "sby.exe",          ["--version"]),
    ("boolector",        "boolector.exe",    ["--version"]),
    ("z3",               "z3.exe",           ["--version"]),
    ("yices",            "yices.exe",        ["--version"]),
    ("cvc5",             "cvc5.exe",         ["--version"]),
    ("gtkwave",          "gtkwave.exe",      ["--version"]),
]

#: Tools the benchmark needs and that are NOT in this bundle. Reported as
#: absent rather than silently skipped.
NOT_PRESENT = [
    ("OpenSTA",   "STA oracle; needs an SDC-consuming flow"),
    ("OpenROAD",  "physical implementation; heavy"),
    ("Surelog",   "SystemVerilog front end"),
    ("UHDM",      "Universal Hardware Design Model; pairs with Surelog"),
    ("KLayout",   "layout/DRC; no UPF semantics"),
    ("Magic",     "layout/extraction; no UPF semantics"),
    ("Netgen",    "LVS; needs a layout"),
    ("OpenLane",  "full flow; wraps its own OpenROAD"),
]


def _env_with_suite() -> dict:
    """PATH with the bundle's bin/ and lib/ prepended.

    Both are required: bin/ has the executables, lib/ has the DLLs they load
    (libreadline8.dll for yosys, Qt6* for gtkwave).
    """
    env = dict(os.environ)
    parts = [str(SUITE / "bin"), str(SUITE / "lib")]
    if env.get("PATH"):
        parts.append(env["PATH"])
    env["PATH"] = os.pathsep.join(parts)
    return env


def probe(tool: str, exe: str, args: list) -> dict:
    """Run one tool and capture its first version line."""
    path = SUITE / "bin" / exe
    if not path.exists():
        return {"tool": tool, "exe": str(path), "available": False,
                "version": None, "note": "not present in bundle"}
    try:
        proc = subprocess.run([str(path), *args], capture_output=True,
                              text=True, timeout=60, env=_env_with_suite(),
                              cwd=str(SUITE))
    except Exception as exc:  # OSError, timeout
        return {"tool": tool, "exe": str(path), "available": True,
                "version": None, "note": f"launch failed: {type(exc).__name__}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    line = next((ln.strip() for ln in out.splitlines() if ln.strip()), "")
    return {"tool": tool, "exe": str(path), "available": proc.returncode == 0,
            "version": line or None,
            "note": None if proc.returncode == 0 else f"exit {proc.returncode}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true",
                    help="write docs/validation/EDA_ENVIRONMENT.md")
    args = ap.parse_args()

    results = [probe(*t) for t in TOOLS]
    absent = [{"tool": n, "note": why} for n, why in NOT_PRESENT]
    ok = [r for r in results if r["available"] and r["version"]]

    if args.json:
        print(json.dumps({"suite": str(SUITE), "suite_present": SUITE.is_dir(),
                          "probed": results, "not_present": absent}, indent=2))
        return 0

    print(f"Suite: {SUITE}  ({'present' if SUITE.is_dir() else 'MISSING'})")
    print(f"\n{len(ok)} of {len(TOOLS)} probed tools run.\n")
    print("%-22s %-10s %s" % ("TOOL", "RUNNABLE", "VERSION"))
    print("-" * 78)
    for r in results:
        status = "yes" if r["available"] and r["version"] else (
            "FAILED" if r["available"] else "no")
        ver = (r["version"] or r["note"] or "-")
        if len(ver) > 52:
            ver = ver[:52] + "..."
        print("%-22s %-10s %s" % (r["tool"], status, ver))

    print("\nNot available in this environment (relevant to power-intent work):")
    for a in absent:
        print("  %-12s %s" % (a["tool"], a["note"]))

    if args.write:
        out = Path(__file__).resolve().parent.parent / "docs" / "validation" / \
              "EDA_ENVIRONMENT.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# EDA Environment Record", "",
            "> Generated by `scripts/probe_eda.py --write`. Do not hand-edit.",
            f"> Suite: `{SUITE}` (OSS CAD Suite, YosysHQ).", "",
            "The suite is **not on `PATH` by default**. Prepend both `bin/` and",
            "`lib/` — `lib/` is required or the binaries fail to load their DLLs",
            "(`libreadline8.dll` for Yosys).", "",
            "| Tool | Runnable | Version |", "|---|---|---|",
        ]
        for r in results:
            lines.append(f"| {r['tool']} | {'yes' if r['available'] and r['version'] else 'no'} "
                         f"| {r['version'] or r['note'] or '-'} |")
        lines += ["", "## Not available", "",
                  "| Tool | Why it matters here |", "|---|---|"]
        for a in absent:
            lines.append(f"| {a['tool']} | {a['note']} |")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())