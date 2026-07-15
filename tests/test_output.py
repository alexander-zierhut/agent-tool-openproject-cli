"""Output formats (json/table/markdown), per-command --format, and settings."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration


def test_json_default(op):
    res = op(["project", "list"]).ok()
    assert isinstance(res.json, list)  # parses as JSON


def test_markdown_via_global_output(op):
    # -o markdown before the command
    res = op(["project", "list"], output="markdown").ok()
    assert res.stdout.lstrip().startswith("| ID | Identifier")
    assert "| --- |" in res.stdout


def test_format_after_command(op):
    # --format works AFTER the subcommand
    res = op(["project", "list", "--format", "markdown"], output=None).ok()
    assert res.stdout.lstrip().startswith("| ID |")


def test_short_f_after_command(op):
    res = op(["project", "list", "-f", "table"], output=None).ok()
    assert "┏" in res.stdout or "Identifier" in res.stdout  # rich table borders/header


def test_o_after_command(op):
    # -o/--output also works after the subcommand (not just before)
    res = op(["project", "list", "-o", "markdown"], output=None).ok()
    assert res.stdout.lstrip().startswith("| ID |")


def test_markdown_single_object(op):
    res = op(["project", "get", "demo-project"], output="markdown").ok()
    assert res.stdout.lstrip().startswith("| Field | Value |")


def test_settings_set_and_default(op, tmp_path):
    cfg = {"OPCLI_CONFIG_DIR": str(tmp_path)}
    # set default to markdown
    saved = op(["settings", "set-format", "markdown"], env=cfg).ok().json
    assert saved["defaultFormat"] == "markdown"
    # a command with NO explicit format now uses markdown
    res = op(["project", "list"], output=None, env=cfg, stdin="").ok()
    assert res.stdout.lstrip().startswith("| ID |")
    # get-format reflects it
    gf = op(["settings", "get-format"], env=cfg).ok().json
    assert gf["defaultFormat"] == "markdown"


def test_explicit_overrides_saved_default(op, tmp_path):
    cfg = {"OPCLI_CONFIG_DIR": str(tmp_path)}
    op(["settings", "set-format", "markdown"], env=cfg).ok()
    # explicit -o json beats the saved markdown default
    res = op(["project", "list"], output="json", env=cfg).ok()
    assert isinstance(res.json, list)


def test_settings_show(op):
    res = op(["settings", "show"]).ok().json
    assert "configPath" in res and "defaultFormat" in res


# ---- --fields selection ----
def test_fields_json_list(op, wp):
    rows = op(["wp", "list", "--project", "demo-project", "--all", "--limit", "3", "--fields", "id,subject"]).ok().json
    assert rows
    for r in rows:
        assert set(r.keys()) == {"id", "subject"}


def test_fields_json_single_with_dotted(op, wp):
    got = op(["wp", "get", str(wp["id"]), "--fields", "id,project.name"]).ok().json
    assert set(got.keys()) == {"id", "project.name"}
    assert got["id"] == wp["id"]
    assert got["project.name"]  # resolved nested value


def test_fields_markdown_columns(op):
    res = op(["project", "list", "--fields", "identifier", "-f", "markdown"], output=None).ok()
    assert res.stdout.lstrip().startswith("| identifier |")


def test_fields_after_command(op, wp):
    # --fields works after the subcommand too
    got = op(["wp", "get", str(wp["id"]), "--fields", "id"]).ok().json
    assert got == {"id": wp["id"]}
