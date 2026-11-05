"""`report` must work offline and name THIS tool's repo.

Same property as the guide: an installed binary with no README or AGENTS.md
beside it still has to tell a user where a problem is reported. So `report`
reaches no network, needs no token, and cannot fail on config — and it must name
this tool's OWN repo, not a sibling's (a copy-paste slug is the obvious bug).

Hermetic: introspection only.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from opcli import __version__
from opcli.cli import app


def test_report_runs_offline_and_names_this_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("OPCLI_CONFIG_DIR", str(tmp_path / "does-not-exist"))
    monkeypatch.delenv("OPCLI_TOKEN", raising=False)

    result = CliRunner().invoke(app, ["report"])
    assert result.exit_code == 0, result.output

    data = json.loads(result.stdout)
    assert data["repo"] == "alexander-zierhut/agent-tool-openproject-cli"
    assert data["published"] is True
    assert data["version"] == __version__
    assert data["issues"].endswith("/agent-tool-openproject-cli/issues")
    assert "/issues/new?" in data["newIssue"]
    # The running version is pre-filled into the issue body, not just reported.
    assert __version__ in data["newIssue"]


def test_report_names_the_command_users_type(monkeypatch, tmp_path):
    """SPEC.name is "op-cli" (config dir + keyring service), but the report must
    name the installed command, or the issue template asks for `op-cli --version`."""
    import json

    from typer.testing import CliRunner

    from opcli.cli import app

    monkeypatch.setenv("OPCLI_CONFIG_DIR", str(tmp_path / "none"))
    data = json.loads(CliRunner().invoke(app, ["report"]).stdout)
    assert data["tool"] == "openproject"
    assert "openproject --version" in " ".join(data["include"])
    assert "op-cli" not in data["newIssue"]
