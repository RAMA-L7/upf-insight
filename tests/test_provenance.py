"""Finding file-provenance regression tests.

The engine knows the source filename for every command line (CommandRecord),
so findings carrying a ``line`` must resolve their ``file``. Ambiguous lines
(the same line number in multiple files) must stay empty — never invented.
"""

from upf_insight.preprocess.upf_preprocess import preprocess
from upf_insight.engine.engine import validate_records

GOOD = """\
upf_version 3.0
set_design_top top
create_supply_port vdd -direction in
create_supply_net vdd -resolve port
connect_supply_net vdd -ports vdd
create_supply_set primary -function {power vdd}
create_power_domain PD -elements {u0} -primary_supply_set primary
add_port_state vdd -state {ON 1.0}
create_pst pst -supplies {vdd}
add_pst_state RUN -pst pst -state {vdd ON}
"""

BAD = """\
create_power_domain PD -elements {u0} -primary_supply_set missing
set_isolation iso -domain NOPE -isolation_supply missing -clamp_value 0
add_pst_state RUN -pst missing -state {vdd ON}
"""


def _files_with_lines(findings):
    return sorted({(f.file, f.line) for f in findings if f.file})


def test_single_file_findings_resolve_file():
    res = validate_records(preprocess(BAD, file="block_a.upf"))
    assert len(res.check.findings) >= 1
    for f in res.check.findings:
        if f.line:
            assert f.file == "block_a.upf"


def test_clean_file_no_findings():
    res = validate_records(preprocess(GOOD, file="clean.upf"))
    assert res.check.findings == []


def test_multi_file_distinct_lines_resolve_each_file():
    # Both files are broken, but B is padded so its content lines (11-13) do
    # not collide with A's (1-3) — each finding must resolve to its own file.
    recs = preprocess(BAD, file="a.upf") + preprocess("\n" * 10 + BAD, file="b.upf")
    res = validate_records(recs)
    a_lines = {f.line for f in res.check.findings if f.file == "a.upf"}
    b_lines = {f.line for f in res.check.findings if f.file == "b.upf"}
    assert a_lines == {1, 2, 3}
    assert b_lines == {11, 12, 13}
    assert not (a_lines & b_lines)  # distinct source lines -> distinct files


def test_multi_file_colliding_lines_leave_file_empty():
    # Identical content in two files collides on every line number — the
    # provenance is ambiguous and must NOT be invented.
    recs = preprocess(BAD, file="x.upf") + preprocess(BAD, file="y.upf")
    res = validate_records(recs)
    assert len(res.check.findings) >= 1
    for f in res.check.findings:
        if f.line:
            assert f.file == ""


def test_findings_without_line_stay_empty():
    res = validate_records(preprocess(BAD, file="b.upf"))
    # findings with no line keep an empty file (nothing to resolve against)
    for f in res.check.findings:
        if not f.line:
            assert f.file == ""
