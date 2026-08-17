"""Tests for the ``upf-insight whats-new`` release-notes command.

Mirrors the `rta whats-new` flow: offline notes from the wheel, latest
versions by default, full changelog with ``--all``, and an upgrade hint when
the installed version is behind the latest documented release.
"""

from upf_insight import __version__
from upf_insight.cli.cli import main
from upf_insight.engine.meta.release_notes import RELEASE_NOTES, latest_version


def test_whats_new_prints_latest_release(capsys):
    code = main(["whats-new"])
    out = capsys.readouterr().out
    assert code == 0
    assert f"UPF-Insight v{latest_version()} - what changed  (latest)" in out
    assert "You are up to date." in out
    assert "CHANGELOG.md" in out
    # offline notes come from the module, not the repo
    assert RELEASE_NOTES[latest_version()][0]


def test_whats_new_all_prints_earlier_releases(capsys):
    code = main(["whats-new", "--all"])
    out = capsys.readouterr().out
    assert code == 0
    # every documented release appears when --all is used
    for v in RELEASE_NOTES:
        assert f"UPF-Insight v{v} - what changed" in out


def test_release_notes_in_sync_with_version():
    """The newest documented release must equal the installed version so the
    upgrade hint stays honest."""
    assert latest_version() == __version__
