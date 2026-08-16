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


def test_generate_skeleton_is_clean():
    text = generate_skeleton(domains=["core", "io"], always_on=["clk"], retention=["core"])
    _assert_clean(_check(text))


def test_generate_upf_isolation():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core"), DomainParam("io")],
        isolation=[IsolationParam("io", clamp_value="0", signal="iso_en",
                                  isolation_supply="vdd_iso")],
    ))
    assert "set_isolation iso_io -domain io -isolation_supply vdd_iso" in text
    assert "-clamp_value 0" in text
    assert "-isolation_signal iso_en" in text
    assert "create_supply_net vdd_iso" in text
    _assert_clean(_check(text))


def test_generate_upf_switch():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core")],
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
    assert "set_level_shifter ls_io -domain io -location self" in text
    assert "-threshold 0.8" in text
    assert "-rule low_to_high" in text
    _assert_clean(_check(text))


def test_generate_upf_retention_and_always_on():
    text = generate_upf(UPFParams(
        domains=[DomainParam("core")],
        retention=[RetentionParam("core")],
        always_on=["clk", "rst"],
    ))
    assert "set_retention ret_core -domain core" in text
    assert "-save_signal save" in text and "-restore_signal restore" in text
    assert "set_port_attributes clk, rst -attribute {always_on true}" in text
    _assert_clean(_check(text))


def test_generate_upf_full_round_trip():
    text = generate_upf(UPFParams(
        design_top="soc_top",
        domains=[DomainParam("core", "u_core"), DomainParam("io", "u_io")],
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