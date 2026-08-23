"""Tests for the UPF generator (upf_insight/generate/generator.py).

The key contract: generated UPF must round-trip through the validator with
zero errors and no unsupported commands, so a user can generate and immediately
validate.
"""

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from upf_insight.generate.generator import (
    UPFParams,
    DomainParam,
    SwitchParam,
    IsolationParam,
    LevelShifterParam,
    RetentionParam,
    generate_upf,
    generate_skeleton,
)
from upf_insight.preprocess.upf_preprocess import preprocess
from upf_insight.engine.engine import validate_records


def _check(text):
    return validate_records(preprocess(text, file="<generated>"))


def _single(text):
    """Join Tcl line continuations so single-line assertions work on the
    multi-line generated output: a line ending in ``\\`` continues onto the
    next line (``create_power_switch sw \\\n    -domain`` becomes
    ``create_power_switch sw -domain``)."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while line.endswith("\\") and i + 1 < len(lines):
            i += 1
            line = line[:-1].strip() + " " + lines[i].strip()
        out.append(line)
        i += 1
    return "\n".join(out)



def _assert_clean(result):
    codes = [f.rule for f in result.check.findings if f.severity == "error"]
    assert codes == [], f"generator emitted errors: {codes}"
    assert result.support.statuses["UNSUPPORTED"] == 0


def test_generate_upf_default_is_clean():
    text = generate_upf(UPFParams())
    assert "upf_version 3.0" in text
    assert "create_power_domain core" in text
    assert "create_pst pst_top" in text
    _assert_clean(_check(text))


def test_generate_output_is_multiline():
    """Long commands are emitted as Tcl line continuations for readability,
    and the validator joins them back into the same logical commands."""
    text = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out")],
        switches=[SwitchParam("sw_core", "core", "vdd_sw_in", "vdd_sw_out", "iso_ctrl")],
    ))
    assert "\\\n" in text, "expected a line continuation for long commands"
    # the validator round-trips the continuation exactly like a single line
    single = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out")],
        switches=[SwitchParam("sw_core", "core", "vdd_sw_in", "vdd_sw_out", "iso_ctrl")],
    ))
    _assert_clean(_check(text))
    a = _check(text).check.to_dict()
    b = _check(single).check.to_dict()
    assert [f["rule"] for f in a["findings"]] == [f["rule"] for f in b["findings"]]


def test_generate_skeleton_is_clean():
    text = generate_skeleton(domains=["core", "io"], always_on=["clk"], retention=["core"])
    _assert_clean(_check(text))


def test_generate_upf_isolation():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core"), DomainParam("io")],
        isolation=[IsolationParam("io", clamp_value="0", signal="iso_en",
                                  isolation_supply="vdd_iso")],
    ))
    flat = _single(text)
    assert "set_isolation iso_io -domain io -isolation_supply vdd_iso" in flat
    assert "-clamp_value 0" in flat
    # the control signal is its own command, never folded into set_isolation
    assert "set_isolation_control iso_io -domain io -isolation_signal iso_en" in flat
    assert "create_supply_net vdd_iso" in text
    _assert_clean(_check(text))


def test_generate_upf_switch():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out")],
        switches=[SwitchParam("sw_core", "core", "vdd_sw_in", "vdd_sw_out", "iso_ctrl")],
    ))
    assert "create_power_switch sw_core" in text
    assert "-input_supply_port vdd_sw_in" in text
    assert "-output_supply_port vdd_sw_out" in text
    assert "-control_port iso_ctrl" in text
    assert "add_pst_state sw_core.off" in text
    result = _check(text)
    _assert_clean(result)
    model = result.check.model
    switch = next(iter(model.switches.values()))
    assert switch.input_supply == "vdd_sw_in"
    assert switch.output_supply == "vdd_sw_out"
    assert switch.control_port == "iso_ctrl"


def test_generate_upf_level_shifter():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core"), DomainParam("io")],
        level_shifters=[LevelShifterParam("io", location="self", threshold="0.8",
                                          rule="low_to_high")],
    ))
    flat = _single(text)
    assert "set_level_shifter ls_io -domain io -location self" in flat
    assert "-threshold 0.8" in flat
    assert "-rule low_to_high" in flat
    _assert_clean(_check(text))


def test_generate_upf_retention_and_always_on():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core")],
        retention=[RetentionParam("core")],
        always_on=["clk", "rst"],
    ))
    flat = _single(text)
    assert "set_retention ret_core -domain core -retention_supply retention" in flat
    # save/restore live in the dedicated control command, with explicit
    # active-sense polarity so the intent is unambiguous
    assert "set_retention_control ret_core -domain core -save_signal {save high}" in flat
    assert "-restore_signal {restore low}" in flat
    assert "set_port_attributes clk, rst -attribute {always_on true}" in text
    _assert_clean(_check(text))


def test_generate_upf_full_round_trip():
    text = generate_upf(UPFParams(
        design_top="soc_top",
        domains=[DomainParam("core", "u_core", primary_power="vdd_sw_out"), DomainParam("io", "u_io")],
        switches=[SwitchParam("sw_core", "core", "vdd_sw_in", "vdd_sw_out", "iso_ctrl")],
        isolation=[IsolationParam("io", clamp_value="0", signal="iso_en")],
        level_shifters=[LevelShifterParam("io", location="inout", threshold="0.8")],
        retention=[RetentionParam("core")],
        always_on=["clk", "rst"],
    ))
    result = _check(text)
    _assert_clean(result)
    model = result.check.model
    assert {d.name for d in model.domains.values()} >= {"core", "io"}
    assert len(model.isolation) == 1
    assert len(model.level_shifters) == 1
    assert len(model.retentions) == 1


def test_generate_upf_validation_errors():
    with pytest.raises(ValueError):
        generate_upf(UPFParams(domains=[]))
    with pytest.raises(ValueError):
        generate_upf(UPFParams(domains=[DomainParam("core"), DomainParam("core")]))
    with pytest.raises(ValueError):
        generate_upf(UPFParams(
            domains=[DomainParam("core")],
            isolation=[IsolationParam("nope")],
        ))
    with pytest.raises(ValueError):
        generate_upf(UPFParams(
            domains=[DomainParam("core")],
            switches=[SwitchParam("sw", "nope", "a", "b", "c")],
        ))
    with pytest.raises(ValueError):
        generate_upf(UPFParams(pst_states=[]))


def test_cli_generate_prints_constructs(capsys):
    from upf_insight.cli.cli import main

    code = main(["generate", "--domains", "core,io",
                 "--switch", "sw_core:core:vdd_sw_in:vdd_sw_out:iso_ctrl",
                 "--isolation", "io:0:vdd_iso:iso_en",
                 "--level-shifter", "io:self:0.8",
                 "--retention", "core"])
    assert code == 0
    out = capsys.readouterr().out
    assert "create_power_switch sw_core" in out
    assert "set_isolation iso_io" in out
    assert "set_level_shifter ls_io" in out
    assert "set_retention ret_core" in out


def test_cli_generate_bad_spec_returns_2(capsys):
    from upf_insight.cli.cli import main

    code = main(["generate", "--switch", "broken"])
    assert code == 2


def test_api_generate_post_returns_content():
    from upf_insight.api import api_server

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), api_server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        params = {
            "design_top": "top",
            "domains": [{"name": "core"}, {"name": "io"}],
            "isolation": [{"domain": "io", "clamp_value": "0"}],
            "level_shifters": [{"domain": "io", "location": "self", "threshold": "0.8"}],
            "retention": [{"domain": "core"}],
            "always_on": ["clk"],
        }
        req = Request(base + "/api/generate", data=json.dumps({"params": params}).encode(),
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
        assert "content" in body
        assert "create_power_domain core" in body["content"]
        assert "set_isolation iso_io" in body["content"]
        _assert_clean(_check(body["content"]))
    finally:
        httpd.shutdown()


def test_api_generate_bad_params_returns_400():
    from upf_insight.api import api_server

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), api_server.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        req = Request(base + "/api/generate", data=json.dumps({"params": {"domains": []}}).encode(),
                      headers={"Content-Type": "application/json"})
        with pytest.raises(Exception) as ei:
            urlopen(req, timeout=5)
        assert ei.value.code == 400
        err = json.loads(ei.value.read())
        assert "error" in err
    finally:
        httpd.shutdown()

def test_generate_isolation_has_explicit_applies_to():
    """Audit fix: isolation strategies carry explicit boundary direction
    (-applies_to outputs) instead of relying on UPF defaults."""
    text = generate_upf(UPFParams(
        domains=[DomainParam("core"), DomainParam("io")],
        isolation=[IsolationParam("io", clamp_value="0", signal="iso_en")],
    ))
    flat = _single(text)
    assert "set_isolation iso_io -domain io -isolation_supply vdd_iso" in flat
    assert "-applies_to outputs" in flat
    _assert_clean(_check(text))


def test_generate_switchable_domain_uses_parent_location():
    """Audit fix: isolation and level shifters on a switchable domain must
    live in the always-on parent - at `self` they would lose power (UPF-063)."""
    text = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out",
                             domain_type="switchable"),
                 DomainParam("io", domain_type="always_on")],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out", "pwr_en")],
        isolation=[IsolationParam("core", clamp_value="0", signal="iso_en")],
        level_shifters=[LevelShifterParam("core", rule="low_to_high",
                                          threshold="0.8")],
    ))
    flat = _single(text)
    assert "set_isolation iso_core -domain core -isolation_supply vdd_iso" in flat
    assert "set_isolation iso_core -domain core -isolation_supply vdd_iso" in flat
    # the generator overrides self -> parent for switchable domains
    assert "-location parent" in flat
    assert "set_level_shifter ls_core -domain core -location parent" in flat
    res = _check(text)
    codes = [f.rule for f in res.check.findings if f.severity == "error"]
    assert "UPF-063" not in codes


def test_generate_retention_has_elements_and_polarity():
    """Audit fix: retention names explicit elements and save/restore polarity,
    not just a domain-wide strategy shell."""
    text = generate_upf(UPFParams(
        domains=[DomainParam("core", elements="u_core")],
        retention=[RetentionParam("core", elements="regA regB",
                                  save_signal="save", restore_signal="restore",
                                  save_sense="high", restore_sense="low")],
    ))
    flat = _single(text)
    assert "set_retention ret_core -domain core -retention_supply retention" in flat
    assert "-elements {regA regB}" in flat
    assert "set_retention_control ret_core -domain core -save_signal {save high}" in flat
    assert "-restore_signal {restore low}" in flat
    res = _check(text)
    assert res.check.model.retentions[0].elements == ["regA", "regB"]
    assert res.check.model.retentions[0].save_signal == "{save high}"
    assert res.check.model.retentions[0].restore_signal == "{restore low}"
    _assert_clean(res)


def test_generate_voltage_grounds_pst_and_detects_crossing():
    """Audit fix: per-domain voltage flows into the PST ON values, and the
    validator detects a missing level shifter across different voltages
    (UPF-061) - the generator must add one to be clean."""
    text = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out", voltage="0.8",
                             domain_type="switchable"),
                 DomainParam("io", voltage="1.0", domain_type="always_on")],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out", "pwr_en")],
    ))
    # the low-voltage domain's supply is declared at 0.8V
    assert "add_port_state vdd_sw_out" in text
    assert "-state {ON 0.8}" in text
    # no level shifter -> the validator must flag the crossing
    codes = {f.rule for f in _check(text).check.findings}
    assert "UPF-061" in codes
    # adding the level shifter resolves the crossing (with parent location)
    text2 = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out", voltage="0.8",
                             domain_type="switchable"),
                 DomainParam("io", voltage="1.0", domain_type="always_on")],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out", "pwr_en")],
        level_shifters=[LevelShifterParam("core", rule="low_to_high",
                                          threshold="0.8")],
    ))
    codes2 = [f.rule for f in _check(text2).check.findings if f.severity == "error"]
    assert "UPF-061" not in codes2
    assert "UPF-063" not in codes2


def test_generate_default_pst_is_clean_and_meaningful():
    """Audit fix: the default PST has an ALL_ON row (no fake PS_OFF with the
    switch output ON while VDD is OFF) and only declares port states that are
    actually used (no UPF-030)."""
    text = generate_upf(UPFParams(
        domains=[DomainParam("core", primary_power="vdd_sw_out",
                             domain_type="switchable")],
        switches=[SwitchParam("sw_core", "core", "vdd", "vdd_sw_out", "pwr_en")],
    ))
    flat = _single(text)
    assert "add_pst_state ALL_ON" in flat
    # the switch-off row models the physically meaningful gated state:
    # VDD ON, switch output OFF
    assert "add_pst_state sw_core.off -pst pst_top -state {vdd ON vss ON vdd_sw_out OFF}" in flat
    res = _check(text)
    codes = [f.rule for f in res.check.findings if f.severity == "error"]
    assert "UPF-030" not in codes
    assert "UPF-061" not in codes


def test_cli_generate_voltage_and_retention_spec(capsys):
    """CLI exposes the audit fixes: --domain-voltage grounds the PST and
    --retention-spec carries elements + polarity."""
    from upf_insight.cli.cli import main

    code = main(["generate", "--domains", "core,io",
                 "--domain-type", "core:switchable",
                 "--domain-voltage", "core:0.8",
                 "--switch", "sw_core:core:vdd:vdd_sw_out:pwr_en",
                 "--retention-spec", "core:vdd_ret:save:restore:regA,regB"])
    assert code == 0
    out = capsys.readouterr().out
    assert "-state {ON 0.8}" in out
    assert "-elements {regA regB}" in out
    assert "-save_signal {save high}" in out
