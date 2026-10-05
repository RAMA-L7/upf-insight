#!/usr/bin/env python
"""Canonical external-corpus definitions and file enumeration.

Two harnesses measure the same external UPF corpora: ``validate_external.py``
(parser/normalization/semantic classification) and ``adjudicate.py`` (finding
inventory and verdicts). When they enumerate the corpus differently they
produce different numbers for the same load set, which makes every reported
figure ambiguous. This module is the single source of truth for *which files
are in a corpus and in what order*, so the two harnesses cannot drift.

Why a shared module rather than one importing the other: ``adjudicate.py``
deliberately has no import-order coupling with the CLI harness (it is meant to
be runnable and readable standalone), and ``validate_external.py`` shells out
to subprocesses. A leaf module that neither imports is the only structure that
satisfies both constraints.

Ordering is pinned explicitly rather than left to ``sorted()``. ``sorted()``
over ``Path`` objects compares via the OS-specific case-folded flavour, while
``sorted()`` over ``str`` compares byte-wise; on Windows those disagree for
mixed-case filenames (``RamPartitioned_FreePDK.upf`` vs ``RamPartitionedAL.upf``).
Because ``set_scope`` and ``load_upf`` are positional, enumeration order is
semantically significant — it selects which same-named object wins. The key
below is therefore a plain, explicit, case-sensitive collation applied to the
POSIX-style relative path, which is stable across platforms and independent of
the host filesystem's collation rules.

Measured on AnyCore (37 files), all of these yield the same 1546 load-set
findings; ordering is pinned so that agreement is a property of the code rather
than a coincidence of this corpus.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

#: Known external corpora. ``root`` is a local checkout; ``repo``/``commit``
#: record provenance so a reader can re-acquire the exact revision independently.
CORPORA: Dict[str, dict] = {
    "anycore": {
        "root": r"D:\upf-bench\anycore-riscv-src",
        "glob": "power_spec/*.upf",
        "repo": "https://github.com/anycore/anycore-riscv-src",
        "commit": "419cc6cd1e709018de91b32285e79441c1c8c560",
        "license": "NCSU copyright (see LICENSE)",
        "baseline": {"files": 37, "findings": 4012, "fp_rate": 65.0},
    },
    "tenstorrent": {
        "root": r"D:\upf-bench\tt",
        "glob": "*.upf",
        "repo": "https://github.com/tenstorrent/tt-metal (local copy)",
        "commit": "local snapshot",
        "license": "Apache-2.0 (SPDX header in file)",
        "baseline": {"files": 1, "findings": 1, "fp_rate": 100.0},
    },
}


def _sort_key(path: Path, root: Path) -> str:
    """Explicit, platform-independent collation for a corpus file.

    Uses the POSIX-style relative path so that the same corpus enumerates
    identically on Windows and POSIX hosts. ``case_sensitive=True`` is the
    default for ``str`` comparison; the explicit kwarg documents the intent and
    guards against a future caller passing a fold.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:  # pragma: no cover - file outside root
        rel = path
    return rel.as_posix()


def enumerate_corpus(name: str) -> Tuple[List[Path], dict]:
    """Return ``(files, spec)`` for one corpus in canonical order.

    ``spec`` is returned unchanged so callers keep access to provenance. An
    absent corpus raises :class:`FileNotFoundError` with the reason attached;
    callers that prefer to report unavailability rather than fail should catch
    it. This is the only supported way to enumerate an external corpus.
    """
    try:
        spec = CORPORA[name]
    except KeyError:
        raise KeyError("unknown corpus %r; known: %s"
                       % (name, ", ".join(sorted(CORPORA)))) from None

    root = Path(spec["root"])
    if not root.is_dir():
        raise FileNotFoundError(
            "corpus root %s does not exist on this host" % root)

    files = sorted(root.glob(spec["glob"]), key=lambda p: _sort_key(p, root))
    if not files:
        raise FileNotFoundError(
            "no files matched %s under %s" % (spec["glob"], root))
    return files, spec


def corpus_paths(name: str) -> List[str]:
    """Canonical order as strings, for APIs that take a path list."""
    files, _ = enumerate_corpus(name)
    return [str(p) for p in files]


def enumerate_all(names: List[str]) -> Dict[str, Tuple[List[Path], dict]]:
    """Enumerate several corpora, preserving the requested order."""
    return {n: enumerate_corpus(n) for n in names}
