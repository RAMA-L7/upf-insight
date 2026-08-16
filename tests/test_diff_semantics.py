"""Semantic-diff provenance tests.

The diff must compare MODEL SEMANTICS, never provenance. Purely textual
edits (comments, blank lines) shift `declared_line` numbers on every model
object; those shifts must not surface as MODIFY changes.
"""

from upf_insight.preprocess.upf_preprocess import preprocess
from upf_insight.model.builder import build_model
from upf_insight.diff.differ import diff_models

BASE = """\
upf_version 3.0
set_design_top top
create_supply_port vdd -direction in
create_supply_port vss -direction in
create_supply_net vdd -resolve port
create_supply_net vss -resolve port
connect_supply_net vdd -ports vdd
connect_supply_net vss -ports vss
create_supply_set primary -function {power vdd} -function {ground vss}
create_power_domain PD -elements {u0} -primary_supply_set primary
add_port_state vdd -state {ON 1.0} -state {OFF 0.0}
create_pst pst -supplies {vdd}
add_pst_state RUN -pst pst -state {vdd ON}
add_pst_state OFF -pst pst -state {vdd OFF}
"""


def _model(text):
    return build_model(preprocess(text))


def test_identical_semantics_no_changes():
    assert diff_models(_model(BASE), _model(BASE)) == []


def test_comment_only_edit_is_not_a_change():
    # Prepending comments shifts every declared_line — provenance, not
    # semantics. The diff must stay empty.
    edited = "# a comment\\n# another comment\\n" + BASE
    assert diff_models(_model(BASE), _model(edited)) == []


def test_blank_line_insertion_is_not_a_change():
    lines = BASE.splitlines()
    lines.insert(5, "")
    lines.insert(9, "")
    assert diff_models(_model(BASE), _model("\n".join(lines))) == []


def test_real_semantic_change_is_reported():
    regressed = BASE.replace(
        "create_power_domain PD -elements {u0} -primary_supply_set primary",
        "create_power_domain PD -elements {u0} -primary_supply_set missing")
    changes = diff_models(_model(BASE), _model(regressed))
    kinds = [(c.kind, c.what, c.name) for c in changes]
    assert ("MODIFY", "domain", "PD") in kinds


def test_added_object_is_reported():
    extended = BASE + "create_power_domain PD2 -elements {u1} -primary_supply_set primary\\n"
    changes = diff_models(_model(BASE), _model(extended))
    assert ("ADD", "domain", "PD2") in [(c.kind, c.what, c.name) for c in changes]
