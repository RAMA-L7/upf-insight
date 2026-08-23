"""Tests for upf_insight.tools: linter, converter, batch runner."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from upf_insight.tools.batch_runner import (
    batch_check,
    batch_report,
    iter_upf_files,
)
from upf_insight.tools.converter import upf_to_dict, upf_to_json, upf_to_yaml
from upf_insight.tools.linter import LintIssue, lint_file, lint_text

GOOD_UPF = """\
upf_version 2.1
set_design_top top
create_power_domain PD_TOP -include_scope
create_supply_net VDD -domain PD_TOP
connect_supply_net VDD -ports {top.u1.P}
"""

BAD_UPF = """\
upf_version 2.1
set_design_top top
create_power_domain PD_CORE -include_scope
set_isolation ISO_CORE -domain PD_MISSING \\
    -isolation_power_net NOPE -isolation_ground_net NOGND \\
    -elements {r1}
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestLintText:
    def test_fixes_tabs_trailing_whitespace_and_case(self) -> None:
        raw = "\tCreate_Power_Domain PD_TOP -include_scope   \n"
        cleaned, issues = lint_text(raw)
        assert cleaned == "    create_power_domain PD_TOP -include_scope\n"
        rules = {i.rule for i in issues}
        assert {"tab-character", "trailing-whitespace",
                "keyword-case"} <= rules

    def test_missing_final_newline_added(self) -> None:
        cleaned, issues = lint_text("set_design_top top")
        assert cleaned.endswith("\n")
        assert any(i.rule == "missing-final-newline" for i in issues)

    def test_collapses_consecutive_blank_lines(self) -> None:
        raw = "set_design_top top\n\n\n\ncreate_power_domain D\n"
        cleaned, issues = lint_text(raw)
        assert "\n\n\n" not in cleaned
        assert any(i.rule == "blank-lines" for i in issues)

    def test_space_after_comma(self) -> None:
        cleaned, issues = lint_text("set_design_top a,b\n")
        assert cleaned == "set_design_top a, b\n"
        assert any(i.rule == "comma-space" for i in issues)

    def test_detects_unbalanced_brace_without_crashing(self) -> None:
        raw = "create_power_domain D -elements {a\n"
        cleaned, issues = lint_text(raw)
        assert any(i.rule == "unbalanced-brace" for i in issues)
        assert "{a" in cleaned

    def test_detects_unbalanced_bracket(self) -> None:
        _, issues = lint_text("set x [foo\n")
        assert any(i.rule == "unbalanced-bracket" for i in issues)

    def test_ignores_braces_inside_comments(self) -> None:
        _, issues = lint_text("# { unbalanced comment\nset_design_top t\n")
        assert not any(i.rule.startswith("unbalanced") for i in issues)

    def test_issues_sorted_deterministically(self) -> None:
        raw = "\tFOO bar  \n\tBAZ qux  \n"
        _, issues = lint_text(raw)
        keys = [(i.line, i.rule) for i in issues]
        assert keys == sorted(keys)

    def test_clean_text_is_unchanged(self) -> None:
        cleaned, issues = lint_text(GOOD_UPF)
        assert cleaned == GOOD_UPF
        assert issues == []


class TestLintFile:
    def test_fix_writes_only_when_changed(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "dirty.upf", "\tSet_Isolation X\n")
        result = lint_file(p, fix=True)
        assert isinstance(result.issues[0], LintIssue)
        assert result.changed is True
        assert p.read_text(encoding="utf-8") == "    set_isolation X\n"

    def test_fix_no_write_when_clean(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "clean.upf", GOOD_UPF)
        before = p.read_text(encoding="utf-8")
        result = lint_file(p, fix=True)
        assert result.changed is False
        assert p.read_text(encoding="utf-8") == before

    def test_check_only_never_writes(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "ro.upf", "\tCreate_Power_Domain D\n")
        result = lint_file(p, check_only=True, fix=True)
        assert result.changed is True
        assert p.read_text(encoding="utf-8").startswith("\t")


class TestConverter:
    def test_dict_contains_expected_commands(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "design.upf", GOOD_UPF)
        d = upf_to_dict(p)
        assert d["file"] == str(p)
        assert d["upf_version"] == "2.1"
        cmds = [c["command"] for c in d["commands"]]
        assert "create_power_domain" in cmds
        dom = next(c for c in d["commands"]
                   if c["command"] == "create_power_domain")
        assert dom["args"] == ["PD_TOP"]
        assert dom["options"] == {"-include_scope": []}
        assert dom["line"] >= 1

    def test_dict_set_isolation_options(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "iso.upf", BAD_UPF)
        d = upf_to_dict(p)
        iso = next(c for c in d["commands"]
                   if c["command"] == "set_isolation")
        assert iso["args"] == ["ISO_CORE"]
        assert iso["options"]["-domain"] == ["PD_MISSING"]
        assert iso["options"]["-elements"] == ["{r1}"]

    def test_json_round_trip(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "j.upf", GOOD_UPF)
        parsed = json.loads(upf_to_json(p))
        assert parsed["upf_version"] == "2.1"
        assert any(c["command"] == "create_power_domain"
                   for c in parsed["commands"])

    def test_yaml_output_parses(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "y.upf", GOOD_UPF)
        parsed = yaml.safe_load(upf_to_yaml(p))
        assert parsed == upf_to_dict(p)


class TestBatchCheck:
    def test_counts_over_good_and_bad(self, tmp_path: Path) -> None:
        _write(tmp_path, "good.upf", GOOD_UPF)
        sub = tmp_path / "sub"
        sub.mkdir()
        _write(sub, "bad.upf", BAD_UPF)
        (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
        result = batch_check(tmp_path)
        assert result.total_files == 2
        assert result.passed + result.failed == 2
        statuses = sorted(e["exit_status"] for e in result.per_file)
        assert all(s in (0, 1, 3) for s in statuses)
        assert len(result.outputs) == 2
        by_file = {Path(e["file"]).name: e for e in result.per_file}
        assert set(by_file) == {"good.upf", "bad.upf"}

    def test_text_output_rendered(self, tmp_path: Path) -> None:
        _write(tmp_path, "good.upf", GOOD_UPF)
        result = batch_check(tmp_path, format="text")
        payload = next(iter(result.outputs.values()))
        assert "UPF-Insight" in payload

    def test_json_output_rendered(self, tmp_path: Path) -> None:
        _write(tmp_path, "good.upf", GOOD_UPF)
        result = batch_check(tmp_path, format="json")
        payload = next(iter(result.outputs.values()))
        parsed = json.loads(payload)
        assert "check" in parsed

    def test_unsupported_format_rejected(self, tmp_path: Path) -> None:
        _write(tmp_path, "good.upf", GOOD_UPF)
        try:
            batch_check(tmp_path, format="xml")
        except ValueError as exc:
            assert "unsupported format" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    def test_iter_upf_files_sorted_recursive(self, tmp_path: Path) -> None:
        _write(tmp_path, "b.upf", GOOD_UPF)
        _write(tmp_path, "a.tcl", GOOD_UPF)
        sub = tmp_path / "nested"
        sub.mkdir()
        _write(sub, "c.UPF", GOOD_UPF)
        (tmp_path / "skip.txt").write_text("x", encoding="utf-8")
        files = iter_upf_files(tmp_path)
        names = [p.name.lower() for p in files]
        assert names == sorted(names)
        assert [p.name for p in files] == ["a.tcl", "b.upf", "c.UPF"]

    def test_unreadable_file_recorded_as_failed(
            self, tmp_path: Path,
            monkeypatch: "object") -> None:
        from upf_insight.tools import batch_runner
        _write(tmp_path, "ok.upf", GOOD_UPF)

        def boom(paths, rules=None, netlist=None):
            raise RuntimeError("disk exploded")

        monkeypatch.setattr(batch_runner, "validate", boom)
        result = batch_check(tmp_path)
        assert result.total_files == 1
        assert result.passed == 0
        assert result.failed == 1
        entry = result.per_file[0]
        assert entry["exit_status"] == 3
        assert "disk exploded" in str(entry.get("error"))


class TestBatchReport:
    def test_writes_index_and_per_file_pages(self, tmp_path: Path) -> None:
        _write(tmp_path, "good.upf", GOOD_UPF)
        out = tmp_path / "reports"
        result = batch_report(tmp_path, out)
        index = out / "index.html"
        assert index.is_file()
        assert result.total_files == 1
        assert len(result.reports) == 2
        assert str(index) in result.reports
        assert result.reports == sorted(result.reports)
        html_text = index.read_text(encoding="utf-8")
        assert "good.upf" in html_text
        pages = [p for p in out.glob("*.html") if p.name != "index.html"]
        assert len(pages) == 1

    def test_report_survives_unreadable_file(
            self, tmp_path: Path,
            monkeypatch: "object") -> None:
        from upf_insight.tools import batch_runner
        _write(tmp_path, "broken.upf", BAD_UPF)

        def boom(paths, rules=None, netlist=None):
            raise RuntimeError("nope")

        monkeypatch.setattr(batch_runner, "validate", boom)
        out = tmp_path / "reports"
        result = batch_report(tmp_path, out)
        assert result.total_files == 1
        assert result.failed == 1
        assert (out / "index.html").is_file()
        assert "ERROR" in (out / "index.html").read_text(encoding="utf-8")

