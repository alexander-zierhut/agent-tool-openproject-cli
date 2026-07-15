"""Tests for the built-in `guide` command (no network, no auth needed)."""

from __future__ import annotations

import subprocess
import sys

import pytest
import typer

from opcli.commands import guide


def test_overview_has_essentials():
    ov = guide.OVERVIEW
    assert "OUTPUT CONTRACT" in ov
    assert "guide <topic>" in ov
    assert "OPCLI_TOKEN" in ov  # tells a headless agent how to auth
    assert "lockVersion" in ov  # key gotcha surfaced
    assert "search fields" in ov  # points at discovery


def test_all_topics_present():
    expected = {"search", "wp", "time", "comments", "projects", "costs",
                "customfields", "output", "auth", "notifications"}
    assert expected <= set(guide.TOPICS)
    # every topic has real content
    for name, text in guide.TOPICS.items():
        assert len(text) > 40, name


def test_guide_overview(capsys):
    guide.guide(None)
    assert "operating guide" in capsys.readouterr().out


def test_guide_topic(capsys):
    guide.guide("search")
    out = capsys.readouterr().out
    assert "search fields" in out and "--where" in out


def test_guide_topic_case_insensitive(capsys):
    guide.guide("SEARCH")
    assert "SEARCH" in capsys.readouterr().out


def test_guide_unknown_topic_exits_2():
    with pytest.raises(typer.Exit) as exc:
        guide.guide("nonsense-topic")
    assert exc.value.exit_code == 2


def test_version_flag_no_auth():
    import os

    from opcli import __version__

    env = {k: v for k, v in os.environ.items() if k not in ("OPCLI_TOKEN", "OPCLI_BASE_URL")}
    proc = subprocess.run([sys.executable, "-m", "opcli", "--version"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0
    assert proc.stdout.strip() == __version__


def test_guide_wired_into_cli_without_auth():
    # runs the real CLI with NO token/base-url configured — guide must still work
    import os

    env = {k: v for k, v in os.environ.items() if k not in ("OPCLI_TOKEN", "OPCLI_BASE_URL")}
    env["OPCLI_CONFIG_DIR"] = "/tmp/op-guide-test-nonexistent"
    proc = subprocess.run(
        [sys.executable, "-m", "opcli", "guide"], capture_output=True, text=True, env=env, input=""
    )
    assert proc.returncode == 0
    assert "OUTPUT CONTRACT" in proc.stdout
