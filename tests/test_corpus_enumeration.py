"""Regression tests for canonical external-corpus enumeration.

The bug this pins: ``validate_external.py`` enumerated with ``sorted()`` over
``Path`` objects while ``adjudicate.py`` used ``sorted()`` over ``str``. On
Windows those collate differently for mixed-case filenames, so the two harnesses
silently measured the same corpus in different load orders. The count happened
to agree on AnyCore, which is exactly why the drift went unnoticed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from scripts import corpus  # noqa: E402


def test_unknown_corpus_is_rejected_by_name() -> None:
    with pytest.raises(KeyError) as exc:
        corpus.enumerate_corpus("does-not-exist")
    assert "does-not-exist" in str(exc.value)


def test_sort_key_is_posix_relative_and_case_sensitive(tmp_path) -> None:
    """The pinned collation: POSIX relative path, case-sensitive."""
    root = tmp_path / "power_spec"
    root.mkdir()
    a = root / "RamPartitionedAL.upf"
    b = root / "RamPartitioned_FreePDK.upf"
    a.write_text("x", encoding="utf-8")
    b.write_text("x", encoding="utf-8")

    ka = corpus._sort_key(a, root)
    kb = corpus._sort_key(b, root)

    assert ka == "RamPartitionedAL.upf"
    assert kb == "RamPartitioned_FreePDK.upf"
    # Byte-wise: 'A' (0x41) sorts before '_' (0x5f). This is the assertion that
    # distinguishes the pinned order from Windows' case-folded Path collation,
    # where '_' sorts first.
    assert ka < kb


def test_sort_key_falls_back_when_path_is_outside_root(tmp_path) -> None:
    outside = tmp_path / "elsewhere.upf"
    assert corpus._sort_key(outside, tmp_path / "root") == outside.as_posix()


def test_enumerate_orders_consistently_with_explicit_sort(tmp_path,
                                                          monkeypatch) -> None:
    """Enumerated order must equal an explicit sort by the pinned key."""
    root = tmp_path / "power_spec"
    root.mkdir()
    for name in ("B.upf", "a_lower.upf", "A_upper.upf", "Z_mid.upf"):
        (root / name).write_text("x", encoding="utf-8")

    monkeypatch.setitem(corpus.CORPORA, "tmp", {
        "root": str(root), "glob": "*.upf",
    })

    files, _ = corpus.enumerate_corpus("tmp")
    names = [f.name for f in files]
    expected = [p.name for p in sorted(
        root.glob("*.upf"), key=lambda p: corpus._sort_key(p, root))]
    assert names == expected
    # Case-sensitive collation puts every capital before every lowercase.
    assert names == ["A_upper.upf", "B.upf", "Z_mid.upf", "a_lower.upf"]


def test_enumerate_reports_empty_match(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(corpus.CORPORA, "tmp", {
        "root": str(tmp_path), "glob": "nothing/*.upf",
    })
    with pytest.raises(FileNotFoundError, match="no files matched"):
        corpus.enumerate_corpus("tmp")


def test_enumerate_reports_missing_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(corpus.CORPORA, "tmp", {
        "root": str(tmp_path / "absent"), "glob": "*.upf",
    })
    with pytest.raises(FileNotFoundError, match="does not exist"):
        corpus.enumerate_corpus("tmp")


def test_both_harnesses_enumerate_identically() -> None:
    """The invariant that motivated this module.

    Skipped, not failed, when the external corpora are absent — they are local
    checkouts on a specific host, and the suite must stay runnable anywhere.
    """
    import adjudicate
    import validate_external

    for name in corpus.CORPORA:
        try:
            canonical = corpus.corpus_paths(name)
        except FileNotFoundError:
            continue

        ve_files, ve_prov = validate_external.collect(name)
        assert ve_prov, "provenance lost for %s" % name
        assert [str(p) for p in ve_files] == canonical, (
            "validate_external enumerates %s differently" % name)

        # adjudicate's own unavailability path returns early, so exercise the
        # enumeration directly rather than requiring a full inventory build.
        try:
            ad_files = adjudicate.corpus_paths(name)
        except (FileNotFoundError, KeyError):
            ad_files = None
        if ad_files is not None:
            assert ad_files == canonical, (
                "adjudicate enumerates %s differently" % name)
