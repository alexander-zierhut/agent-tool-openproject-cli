"""Session context: sticky defaults, override, --no-context, save/use.

Uses an isolated config dir per test so it never pollutes the shared session
config (which every other integration test relies on)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def isolated(tmp_path):
    return {"OPCLI_CONFIG_DIR": str(tmp_path)}


def test_context_scopes_and_overrides(op, project, isolated):
    ident = project["identifier"]
    op(["context", "set", "--project", ident], env=isolated).ok()
    assert op(["context", "show"], env=isolated).ok().json["context"]["project"] == ident

    w = op(["wp", "create", "ctx scoped", "--project", ident], env=isolated).ok().json
    try:
        # no --project -> context scopes the listing to this project
        scoped = op(["wp", "list", "--all"], env=isolated).ok().json
        assert scoped
        assert all((r.get("project") or {}).get("id") == project["id"] for r in scoped)
        assert any(r["id"] == w["id"] for r in scoped)

        # explicit flag overrides the context
        demo = op(["wp", "list", "--project", "demo-project", "--all"], env=isolated).ok().json
        assert all((r.get("project") or {}).get("name") == "Demo project" for r in demo)

        # --no-context ignores the context entirely (demo WPs appear)
        allrows = op(["--no-context", "wp", "list", "--all"], env=isolated).ok().json
        assert any((r.get("project") or {}).get("name") == "Demo project" for r in allrows)
    finally:
        op(["wp", "delete", str(w["id"]), "-y"], env=isolated)


def test_context_save_clear_use(op, isolated):
    op(["context", "set", "--project", "demo-project", "--assignee", "me"], env=isolated).ok()
    op(["context", "save", "s1"], env=isolated).ok()
    op(["context", "clear"], env=isolated).ok()
    assert op(["context", "show"], env=isolated).ok().json["context"] == {}

    op(["context", "use", "s1"], env=isolated).ok()
    ctx = op(["context", "show"], env=isolated).ok().json["context"]
    assert ctx["project"] == "demo-project" and ctx["assignee"] == "me"

    names = [r["name"] for r in op(["context", "list"], env=isolated).ok().json]
    assert "s1" in names


def test_context_unset(op, isolated):
    op(["context", "set", "--project", "demo-project", "--status", "open"], env=isolated).ok()
    op(["context", "unset", "status"], env=isolated).ok()
    ctx = op(["context", "show"], env=isolated).ok().json["context"]
    assert "status" not in ctx and ctx["project"] == "demo-project"
