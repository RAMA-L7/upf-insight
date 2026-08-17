"""UPF-Insight CLI.

Command surface (mirrors sdc-tools `cli`):
    upf-insight check FILE [FILE...] [--rule ...] [--format text|json|junit]
                             [--save-baseline base.json]
                             [--baseline base.json --gate POLICY]
    upf-insight model FILE [FILE...] -o out.json
    upf-insight pst   FILE [FILE...] [--json]
    upf-insight coverage FILE [FILE...] [--json]
    upf-insight report FILE [FILE...] [--output report.html]
    upf-insight diff  OLD UPF NEW UPF
    upf-insight generate [--domains ...] [--always-on ...] [--retention ...]
    upf-insight rules [list]
    upf-insight whats-new [--all]
    upf-insight web   [--port N]

Exit-code contract for CI (mirrors sdc-tools):
    0 pass · 1 gate failed · 2 invalid invocation · 3 engine failure
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .. import __version__
from ..engine.engine import validate
from ..report.reporter import format_text, format_json, format_junit, format_html


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="upf-insight",
                                description="Deterministic power-intent "
                                            "intelligence for IEEE 1801 (UPF).")
    p.add_argument("--version", action="version", version=f"upf-insight {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    ck = sub.add_parser("check", help="validate UPF power-intent files")
    ck.add_argument("files", nargs="+")
    ck.add_argument("--upf-version", help="target UPF version (2.1|3.0|4.0)")
    ck.add_argument("--netlist", metavar="JSON",
                    help="design context (netlist snapshot) enabling "
                         "UPF-080..084")
    ck.add_argument("--format", choices=["text", "json", "junit"],
                    default="text")
    ck.add_argument("--rule", action="append", default=[],
                    help="only run these rules (repeatable, e.g. --rule UPF-040)")
    ck.add_argument("--save-baseline", metavar="JSON",
                    help="write the current result as a baseline snapshot")
    ck.add_argument("--baseline", metavar="JSON",
                    help="compare against a saved baseline snapshot")
    ck.add_argument("--gate", metavar="POLICY",
                    help="gate policy: BLOCKERS_ONLY | NO_READINESS_REGRESSION "
                         "| STRICT, or a policy JSON file")

    md = sub.add_parser("model", help="dump the power-intent model as JSON")
    md.add_argument("files", nargs="+")
    md.add_argument("-o", "--output", help="output JSON file (default stdout)")

    ps = sub.add_parser("pst", help="analyze the Power State Table")
    ps.add_argument("files", nargs="+")
    ps.add_argument("--json", action="store_true")

    cv = sub.add_parser("coverage", help="structural domain/supply coverage")
    cv.add_argument("files", nargs="+")
    cv.add_argument("--json", action="store_true")

    rp = sub.add_parser("report", help="generate a human-readable report")
    rp.add_argument("files", nargs="+")
    rp.add_argument("-o", "--output", help="output file (.html)")
    rp.add_argument("--format", choices=["html", "text", "json"],
                    default="html")

    df = sub.add_parser("diff", help="semantic UPF diff between two versions")
    df.add_argument("old")
    df.add_argument("new")

    gn = sub.add_parser("generate", help="generate standard UPF power-intent constructs")
    gn.add_argument("--domains", default="core,io,sram",
                    help="comma-separated domain names")
    gn.add_argument("--domain-type", action="append", default=[],
                    metavar="NAME:TYPE",
                    help="domain power type (NAME:always_on|switchable) - "
                         "repeatable; absent means UNKNOWN (evidence-based)")
    gn.add_argument("--domain-power", action="append", default=[],
                    metavar="NAME:POWER[:GROUND]",
                    help="per-domain primary power net (repeatable)")
    gn.add_argument("--always-on", default="clk,rst",
                    help="comma-separated always-on signals")
    gn.add_argument("--retention", default="",
                    help="comma-separated domain names needing retention")
    gn.add_argument("--design-top", default="top", help="design top module name")
    gn.add_argument("--switch", action="append", default=[],
                    metavar="NAME:DOMAIN:IN:OUT:CTRL",
                    help="add a power switch (repeatable)")
    gn.add_argument("--isolation", action="append", default=[],
                    metavar="DOMAIN[:CLAMP[:SUPPLY[:SIGNAL]]]",
                    help="add an isolation strategy (repeatable)")
    gn.add_argument("--level-shifter", action="append", default=[],
                    metavar="DOMAIN[:LOC[:THRESHOLD]]",
                    help="add a level shifter (repeatable)")
    gn.add_argument("--relation", action="append", default=[],
                    metavar="FROM:TO[:KINDS]",
                    help="add a domain relation (repeatable; KINDS comma-separated, default isolation)")
    gn.add_argument("--architecture", choices=["flat", "hierarchical"],
                    default="flat", help="generation architecture")
    gn.add_argument("--hierarchy", default="",
                    help="comma-separated child scopes for hierarchical mode")
    gn.add_argument("-o", "--output", metavar="UPF",
                    help="write the generated UPF to a file (default stdout)")

    rel = sub.add_parser("relations",
                         help="show the power-domain relation graph (matrix, types, evidence)")
    rel.add_argument("files", nargs="+")
    rel.add_argument("--json", action="store_true",
                     help="emit machine-readable relation JSON")

    rl = sub.add_parser("rules", help="inspect the rule registry")
    rl_sub = rl.add_subparsers(dest="rules_cmd")
    rl_list = rl_sub.add_parser("list", help="list all registered rules")
    rl_list.add_argument("--layer", help="filter by layer (SYNTAX|REFERENCE|"
                                         "SUPPLY_DOMAIN|PST|STRATEGY|DESIGN)")
    rl.add_argument("--layer", help="filter by layer (SYNTAX|REFERENCE|"
                                    "SUPPLY_DOMAIN|PST|STRATEGY|DESIGN)")

    wn = sub.add_parser("whats-new",
                        help="Show what changed in recent releases (offline)")
    wn.add_argument("--all", action="store_true",
                    help="print the full changelog from the terminal")

    web = sub.add_parser("web", help="launch the local workspace")
    web.add_argument("--port", type=int, default=8585)
    return p


def _run_whats_new(args) -> int:
    """Print recent release notes so engineers can see what changed.

    Mirrors the `rta whats-new` flow: the notes ship inside the wheel so this
    works offline; `--all` prints the full changelog."""
    from ..engine.meta.release_notes import RELEASE_NOTES, latest_version

    versions = list(RELEASE_NOTES)
    if not args.all:
        versions = versions[:3]
    for i, v in enumerate(versions):
        header = f"UPF-Insight v{v} - what changed"
        if i == 0:
            header += "  (latest)"
        print(header)
        bullets = RELEASE_NOTES[v]
        if not bullets:
            print("  (no release notes)")
        for b in bullets:
            print(f"  * {b}")
        print()
    if not args.all and latest_version() != __version__:
        print(f"You are on v{__version__}. Upgrade with:")
        print("  pip install -U upf-insight")
    elif latest_version() == __version__:
        print("You are up to date.")
    print("Full changelog: "
          "https://github.com/RAMA-L7/upf-insight/blob/main/CHANGELOG.md")
    return 0


def _load_policy(args_gate: str) -> tuple[str, Optional[dict]]:
    """Return (policy_name, raw_policy) from a gate arg (builtin or file)."""
    try:
        with open(args_gate, "r", encoding="utf-8") as fh:
            return "CUSTOM", json.load(fh)
    except FileNotFoundError:
        return args_gate, None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid policy JSON in {args_gate}: {exc}") from exc


def _run_check(args) -> int:
    result = validate(args.files, rules=args.rule or None, netlist=args.netlist)

    if args.save_baseline:
        with open(args.save_baseline, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, indent=2, default=str)

    if args.gate or args.baseline:
        from ..engine.policy.policy_engine import apply_policy

        baseline = None
        if args.baseline:
            with open(args.baseline, "r", encoding="utf-8") as fh:
                baseline = json.load(fh)
        name, raw = _load_policy(args.gate or "BLOCKERS_ONLY")
        gate = apply_policy(name, result.to_dict(), baseline, raw)
        if args.format == "text":
            sys.stdout.write(format_text(result))
            for reason in gate.reasons:
                sys.stdout.write(f"GATE  [{gate.policy}] {reason}\n")
            sys.stdout.write(f"GATE  result: {'PASS' if gate.passed else 'FAIL'}\n")
        elif args.format == "json":
            payload = result.to_dict()
            payload["gate"] = gate.to_dict()
            sys.stdout.write(json.dumps(payload, indent=2, default=str))
        else:
            sys.stdout.write(format_junit(result))
        return gate.exit_code

    if args.format == "json":
        sys.stdout.write(format_json(result))
    elif args.format == "junit":
        sys.stdout.write(format_junit(result))
    else:
        sys.stdout.write(format_text(result))
    return 0 if result.clean else 1


def _run_model(args) -> int:
    result = validate(args.files)
    payload = result.to_dict()
    payload["model"] = (
        result.check.model.to_dict() if result.check.model else None
    )
    text = json.dumps(payload, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text + "\n")
    return 0


def _run_pst(args) -> int:
    result = validate(args.files)
    if args.json:
        sys.stdout.write(result.to_json())
    else:
        lines = ["Power State Table analysis", "===============================", ""]
        pst = result.pst
        lines.append(f"PST:            {pst.pst_name or '(none)'}")
        lines.append(f"States:         {pst.state_count}")
        lines.append(f"Unused states:  {', '.join(pst.unused_states) or '(none)'}")
        lines.append(f"Undeclared:     {', '.join(pst.undeclared_states) or '(none)'}")
        lines.append(f"Transitions:    {len(pst.transitions)}")
        lines.append("")
        lines.append(pst.coverage_note)
        sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _run_coverage(args) -> int:
    result = validate(args.files)
    if args.json:
        payload = result.to_dict()
        sys.stdout.write(json.dumps(payload["coverage"], indent=2, default=str))
    else:
        cov = result.coverage
        lines = ["Power-intent coverage", "=====================",
                 f"Domain coverage: {cov.domain_coverage}",
                 f"Supply coverage: {cov.supply_coverage}"]
        for d in cov.domains:
            status = "covered" if d.covered else "GAPS: " + ", ".join(d.gaps)
            lines.append(f"  {d.domain}: {status}")
        if cov.unreferenced_supplies:
            lines.append("Unreferenced supplies: "
                         + ", ".join(cov.unreferenced_supplies))
        sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _run_report(args) -> int:
    result = validate(args.files)
    if args.format == "html":
        text = format_html(result)
    elif args.format == "json":
        text = format_json(result)
    else:
        text = format_text(result)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text + "\n")
    return 0


def _run_diff(args) -> int:
    from ..diff.differ import diff_files

    changes = diff_files(args.old, args.new)
    for change in changes:
        print(change)
    return 0


def _run_generate(args) -> int:
    from ..generate.generator import (
        UPFParams,
        DomainParam,
        SwitchParam,
        IsolationParam,
        LevelShifterParam,
        RetentionParam,
        RelationParam,
        generate_upf,
        generate_project,
    )

    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    types = {}
    for spec in args.domain_type:
        parts = [s.strip() for s in spec.split(":")]
        if len(parts) != 2 or parts[1] not in ("always_on", "switchable"):
            print(f"invalid --domain-type (need NAME:always_on|switchable): "
                  f"{spec}", file=sys.stderr)
            return 2
        types[parts[0]] = parts[1]
    powers = {}
    for spec in args.domain_power:
        parts = [s.strip() for s in spec.split(":")]
        if len(parts) < 2 or not parts[0]:
            print(f"invalid --domain-power (need NAME:POWER[:GROUND]): {spec}",
                  file=sys.stderr)
            return 2
        powers[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else "")
    params = UPFParams(
        design_top=args.design_top,
        domains=[
            DomainParam(d, domain_type=types.get(d, ""),
                        primary_power=powers.get(d, ("", ""))[0],
                        primary_ground=powers.get(d, ("", ""))[1])
            for d in domains
        ],
        always_on=[s.strip() for s in args.always_on.split(",") if s.strip()],
        retention=[RetentionParam(d) for d in args.retention.split(",") if d.strip()],
    )
    for spec in args.switch:
        parts = [s.strip() for s in spec.split(":")]
        if len(parts) != 5 or not all(parts):
            print(f"invalid --switch spec (need NAME:DOMAIN:IN:OUT:CTRL): {spec}",
                  file=sys.stderr)
            return 2
        params.switches.append(SwitchParam(*parts))
    for spec in args.isolation:
        parts = [s.strip() for s in spec.split(":")]
        if len(parts) < 1 or not parts[0]:
            print(f"invalid --isolation spec (need DOMAIN[:CLAMP[:SUPPLY[:SIGNAL]]]): {spec}",
                  file=sys.stderr)
            return 2
        iso = IsolationParam(parts[0])
        if len(parts) > 1 and parts[1]:
            iso.clamp_value = parts[1]
        if len(parts) > 2 and parts[2]:
            iso.isolation_supply = parts[2]
        if len(parts) > 3 and parts[3]:
            iso.signal = parts[3]
        params.isolation.append(iso)
    for spec in args.level_shifter:
        parts = [s.strip() for s in spec.split(":")]
        if len(parts) < 1 or not parts[0]:
            print(f"invalid --level-shifter spec (need DOMAIN[:LOC[:THRESHOLD]]): {spec}",
                  file=sys.stderr)
            return 2
        ls = LevelShifterParam(parts[0])
        if len(parts) > 1 and parts[1]:
            ls.location = parts[1]
        if len(parts) > 2 and parts[2]:
            ls.threshold = parts[2]
        params.level_shifters.append(ls)

    params.architecture = args.architecture
    params.hierarchy = [s.strip() for s in args.hierarchy.split(",") if s.strip()]
    for spec in args.relation:
        parts = [s.strip() for s in spec.split(":")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            print(f"invalid --relation spec (need FROM:TO[:KINDS]): {spec}",
                  file=sys.stderr)
            return 2
        kinds = parts[2] if len(parts) > 2 and parts[2] else "isolation"
        params.relations.append(RelationParam(parts[0], parts[1], kinds))
    try:
        if params.architecture == "hierarchical":
            project = generate_project(params)
            if args.output:
                out_dir = args.output.rstrip("/")
                import os

                os.makedirs(out_dir, exist_ok=True)
                for name, text in sorted(project.items()):
                    with open(os.path.join(out_dir, name), "w",
                              encoding="utf-8", newline="\n") as fh:
                        fh.write(text)
                print(f"wrote {len(project)} file(s) to {out_dir}/")
                return 0
            for name, text in sorted(project.items()):
                sys.stdout.write(f"# ==== {name} ====\n{text}")
            return 0
        text = generate_upf(params)
    except ValueError as exc:
        print(f"generate: {exc}", file=sys.stderr)
        return 2
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


def _run_relations(args) -> int:
    result = validate(args.files)
    rel = result.relations
    if rel is None:
        sys.stdout.write("No relation data available.\n")
        return 0
    if args.json:
        sys.stdout.write(json.dumps(rel.to_dict(), indent=2, default=str) + "\n")
        return 0
    lines = [
        "UPF-INSIGHT - power-domain relations",
        "====================================",
        f"Architecture : {rel.architecture}",
        f"Domains      : {len(rel.domains)}",
        f"Always-On    : {sum(1 for d in rel.domains if d.type == 'ALWAYS_ON')}",
        f"Switchable   : {sum(1 for d in rel.domains if d.type == 'SWITCHABLE')}",
        f"UPF files    : {len(rel.files)}",
        "",
        "DOMAIN RELATIONS",
        "-----------------",
    ]
    if not rel.relations:
        lines.append("(no domain relations detected)")
    for r in rel.relations:
        line = f"{r.from_domain} -> {r.to_domain}     {r.label}"
        ev = r.evidence[0] if r.evidence else None
        if ev is not None:
            loc = f" (L{ev.line})" if ev.line else ""
            line += f"   [{ev.kind}{loc}]"
        lines.append(line)
    lines.append("")
    lines.append("MATRIX")
    names = [d.name for d in rel.domains]
    header = "        " + "".join(f"{n[:10]:>11}" for n in names)
    lines.append(header)
    for f in names:
        row = f"{f[:10]:>8}" + "".join(
            f"{rel.matrix.get(f, {}).get(t, '-'):>11}" for t in names)
        lines.append(row)
    lines.append("")
    lines.append("DOMAINS")
    for d in rel.domains:
        lines.append(f"  {d.name:12} {d.type:10} power={d.primary_power or '-'} "
                     f"related={', '.join(sorted(d.related)) or '-'}")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def _run_rules(args) -> int:
    from ..engine.rules.rules_registry import registered_rules

    rules = registered_rules()
    if args.layer:
        rules = [r for r in rules if r.layer == args.layer.upper()]
    for r in rules:
        sys.stdout.write(f"{r.code:8} {r.severity:7} {r.layer:14} "
                         f"{r.title}\n")
    return 0


def _run_web(args) -> int:
    from ..api.api_server import serve

    return serve(port=args.port)


def main(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dispatch = {
        "check": _run_check,
        "model": _run_model,
        "pst": _run_pst,
        "coverage": _run_coverage,
        "relations": _run_relations,
        "report": _run_report,
        "diff": _run_diff,
        "generate": _run_generate,
        "rules": _run_rules,
        "whats-new": _run_whats_new,
        "web": _run_web,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        return 2
    try:
        return int(fn(args) or 0)
    except FileNotFoundError as exc:
        sys.stderr.write(f"upf-insight: file not found: {exc}\n")
        return 2
    except ValueError as exc:
        sys.stderr.write(f"upf-insight: invalid input: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001 - engine failure must be loud
        sys.stderr.write(f"upf-insight: engine failure: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(main())