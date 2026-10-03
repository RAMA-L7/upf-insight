"""Design-aware validation over a real synthesized netlist.

This is the end-to-end case: RTL -> Yosys -> synthesized netlist -> UPF ->
`validate(..., netlist=...)`. It proves structured UPF arguments normalize to
real design objects before lookup, rather than being compared as literal brace
strings.

Yosys lives in the OSS CAD Suite at ``D:\\tools\\oss-cad-suite`` and is NOT on
``PATH`` by default (see ``scripts/probe_eda.py``). When it is unavailable the
Yosys-dependent tests skip; the normalization assertions run either way,
because they depend only on the parser and the model.

Run just the synthesis case with:
    python scripts/probe_eda.py        # confirm the toolchain is present
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from upf_insight.engine.design.netlist_parser import parse_verilog
from upf_insight.engine.engine import validate

ROOT = Path(__file__).resolve().parent.parent
RTL = ROOT / "tests" / "fixtures" / "soc_top.v"
UPF = ROOT / "tests" / "fixtures" / "soc_top.upf"
SUITE = Path(r"D:\tools\oss-cad-suite")


def _yosys_env() -> dict:
    """PATH with the OSS CAD Suite prepended (binaries need their DLLs)."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([
        str(SUITE / "bin"), str(SUITE / "lib"), env.get("PATH", ""),
    ])
    return env


def _yosys_exe() -> str | None:
    """Absolute path to yosys, or None.

    The OSS CAD Suite is not on PATH by default, so ``shutil.which`` alone
    reports it missing even when it is installed. Resolve the bundle path
    first, then fall back to PATH.
    """
    bundled = SUITE / "bin" / ("yosys.exe" if os.name == "nt" else "yosys")
    if bundled.exists():
        return str(bundled)
    return shutil.which("yosys")


def _yosys_available() -> bool:
    return _yosys_exe() is not None


@pytest.fixture(scope="module")
def synthesized_netlist(tmp_path_factory) -> Path:
    """Run Yosys over the RTL fixture and return the synthesized netlist."""
    if not _yosys_available():
        pytest.skip("Yosys not available (expected at D:\\tools\\oss-cad-suite)")
    out = tmp_path_factory.mktemp("netlist") / "soc_top_synth.v"
    script = tmp_path_factory.mktemp("ys") / "synth.ys"
    script.write_text(
        f"read_verilog {RTL.as_posix()}\n"
        "hierarchy -top soc_top\n"
        "proc\n"
        "opt\n"
        f"write_verilog -noattr {out.as_posix()}\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [_yosys_exe(), "-s", str(script)], capture_output=True, text=True,
        timeout=300, env=_yosys_env(),
    )
    assert proc.returncode == 0, proc.stderr[-800:]
    assert out.exists(), "Yosys produced no netlist"
    return out


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def test_yosys_synthesizes_the_fixture(synthesized_netlist):
    """The RTL fixture must actually elaborate and synthesize."""
    ctx, issues = parse_verilog(str(synthesized_netlist))
    assert not issues, issues
    assert "u_cpu" in ctx.instances
    assert "u_sram" in ctx.instances
    assert "clk" in ctx.ports
    assert "iso_en_cpu" in ctx.ports
    assert "ret_en_cpu" in ctx.ports


# ---------------------------------------------------------------------------
# Normalization: structured UPF arguments resolve to real design objects
# ---------------------------------------------------------------------------

def test_retention_control_normalizes_to_the_real_signal(synthesized_netlist):
    """`-save_signal {ret_en_cpu high}` must resolve to `ret_en_cpu`.

    Comparing the raw token '{ret_en_cpu high}' against the design can never
    match, so a real signal reads as absent.
    """
    result = validate([str(UPF)], netlist=str(synthesized_netlist))
    ret = result.check.model.retentions[0]
    assert ret.save_signal == "{ret_en_cpu high}"     # provenance preserved
    assert ret.save_signal_name == "ret_en_cpu"       # normalized for lookup
    assert ret.save_signal_sense == "high"
    assert ret.restore_signal_name == "ret_en_cpu"
    assert ret.restore_signal_sense == "low"


def test_isolation_control_resolves_to_a_real_design_signal(synthesized_netlist):
    """The isolation control is a plain signal and must resolve."""
    result = validate([str(UPF)], netlist=str(synthesized_netlist))
    iso = result.check.model.isolation[0]
    assert iso.control_signal == "iso_en_cpu"
    unknown = [f.message for f in result.check.findings
               if f.rule == "UPF-081" and "iso_en_cpu" in f.message]
    assert not unknown, unknown


def test_no_false_missing_signal_findings_on_valid_design(synthesized_netlist):
    """Every control in the fixture exists in the design, so UPF-081 is silent.

    This is the assertion that fails when '{sig sense}' tokens are compared as
    literal strings — the defect recorded as D6/UPF-081 in the validation
    report.
    """
    result = validate([str(UPF)], netlist=str(synthesized_netlist))
    missing = [f.message for f in result.check.findings if f.rule == "UPF-081"]
    assert not missing, missing


def test_a_genuinely_unknown_signal_is_still_reported(synthesized_netlist):
    """A control that really is absent from the design must be reported.

    Guards against 'fixing' UPF-081 by suppressing it.
    """
    text = UPF.read_text(encoding="utf-8").replace(
        "-isolation_signal iso_en_cpu", "-isolation_signal no_such_signal")
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.upf"
        bad.write_text(text, encoding="utf-8")
        result = validate([str(bad)], netlist=str(synthesized_netlist))
    missing = [f.message for f in result.check.findings
               if f.rule == "UPF-081" and "no_such_signal" in f.message]
    assert missing, "UPF-081 stopped reporting a genuinely absent signal"


# ---------------------------------------------------------------------------
# Design-aware coverage
# ---------------------------------------------------------------------------

def test_domain_elements_resolve_to_real_instances(synthesized_netlist):
    """Power-domain elements must match instances in the synthesized netlist."""
    result = validate([str(UPF)], netlist=str(synthesized_netlist))
    ctx, _ = parse_verilog(str(synthesized_netlist))
    for name in ("PD_CPU", "PD_SRAM"):
        dom = result.check.model.domains[name]
        assert dom.elements, f"{name} lost its element list"
        for element in dom.elements:
            assert element in ctx.instances, (
                f"{name} element {element} is not an instance in the netlist")


def test_design_coverage_is_computed_with_the_netlist(synthesized_netlist):
    """Supplying a netlist must move the design-aware layer out of 'no context'."""
    without = validate([str(UPF)])
    with_net = validate([str(UPF)], netlist=str(synthesized_netlist))
    assert without.design_coverage.status == "INSUFFICIENT_CONTEXT"
    assert with_net.design_coverage.status != "INSUFFICIENT_CONTEXT"


def test_support_boundary_upgrades_with_a_netlist(synthesized_netlist):
    """Design-aware rules cannot be VALIDATED without a design context."""
    without = validate([str(UPF)])
    with_net = validate([str(UPF)], netlist=str(synthesized_netlist))
    assert without.support.statuses["NETLIST_REQUIRED"] > 0
    assert with_net.support.statuses["NETLIST_REQUIRED"] == 0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_design_aware_validation_is_deterministic(synthesized_netlist):
    """Two runs over the same netlist must produce identical output."""
    a = validate([str(UPF)], netlist=str(synthesized_netlist))
    b = validate([str(UPF)], netlist=str(synthesized_netlist))
    assert [f.rule for f in a.check.findings] == [f.rule for f in b.check.findings]
    assert [f.message for f in a.check.findings] == \
           [f.message for f in b.check.findings]