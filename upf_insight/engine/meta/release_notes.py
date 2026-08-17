"""Release notes for the ``upf-insight whats-new`` command.

This module ships inside the wheel, so ``upf-insight whats-new`` works
offline in any environment - it does not need the git repo or a network
connection. Keep in sync with CHANGELOG.md: append the new version here on
every release (newest first).
"""

from ... import __version__ as _APP_VERSION

#: version -> list of bullet lines describing what changed in that release.
RELEASE_NOTES: dict[str, list[str]] = {
    "0.2.0": [
        "Flat + hierarchical power-intent sprint: Flat UPF and Hierarchical UPF "
        "are now first-class in both the generator and validation. The generator "
        "has an architecture selector (Flat / Hierarchical), per-domain power "
        "types (always_on / switchable, never inferred), a domain-relation "
        "editor, per-child domain ownership and load_upf supply mapping.",
        "Generated flat and hierarchical projects round-trip through validation "
        "and produce the same architecture, domain, supply, hierarchy, relation, "
        "topology and provenance model - verified end-to-end from the CLI.",
        "New canonical Power Domain Relation Matrix derived from the engine "
        "model (ISO / LS / ISO+LS / RET / SW / CTRL) with per-relation "
        "provenance; supply sharing is a separate network view and never a "
        "matrix cell.",
        "Hierarchy analysis: domain ownership (UPF file, scope, owner), "
        "flat-vs-hierarchical architecture detection, and load_upf supply maps "
        "with parent-scope resolution (no more false undefined-supply findings).",
        "Scope-aware supply resolution and per-strategy scope provenance fix "
        "cross-scope relations in child UPF files (same-named supplies in "
        "sibling scopes never cross-resolve).",
        "New validation rules: UPF-099 (supply-map side undefined) and "
        "UPF-100 (loaded UPF file missing), both with provenance.",
        "CLI: upf-insight relations FILE... [--json], generate --architecture "
        "hierarchical with --domain-type/--domain-power/--switch/--relation, "
        "and reports expose architecture, relations, supply sharing, hierarchy "
        "and supply maps in text, JSON and HTML.",
    ],
    "0.1.0": [
        "Initial validation candidate: deterministic UPF power-intent "
        "validation with 67+ rules, readiness scoring, structural coverage, "
        "semantic diff, CI gate (exit 0/1/2/3), HTML/JSON reports and the "
        "feature-first web workspace with Test Drive.",
    ],
}


def latest_version() -> str:
    """Return the newest version with release notes (deterministic)."""
    return max(RELEASE_NOTES)


def installed_version() -> str:
    """Return the installed package version."""
    return _APP_VERSION
