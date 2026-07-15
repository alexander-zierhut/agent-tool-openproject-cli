"""Pytest fixtures for the OpenProject CLI integration suite.

The suite drives the *real* CLI as a subprocess (``python -m opcli``) against a
live OpenProject instance, exactly as an agent would. It requires:

    OPCLI_BASE_URL   e.g. http://localhost:8090
    OPCLI_TOKEN      an API token (the harness/dev provides the admin token)

If those are absent, or the instance is unreachable, the whole integration
suite is skipped. Run `./scripts/seed_test_data.sh` once before the suite so
fresh projects inherit time logging and the test custom fields exist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import Any

import pytest

BASE_URL = os.environ.get("OPCLI_BASE_URL")
TOKEN = os.environ.get("OPCLI_TOKEN")
RUN_ID = uuid.uuid4().hex[:8]


@dataclass
class Result:
    code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> Any:
        return json.loads(self.stdout) if self.stdout.strip() else None

    def ok(self) -> "Result":
        assert self.code == 0, f"command failed ({self.code}): {self.stderr or self.stdout}"
        return self


def _run(
    args: list[str],
    *,
    stdin: str | None = None,
    output: str | None = "json",
    token: str | None = None,
    env: dict | None = None,
) -> Result:
    cmd = [sys.executable, "-m", "opcli"]
    if output is not None:
        cmd += ["-o", output]
    cmd += args
    proc_env = os.environ.copy()
    if token is not None:  # run as a different user
        proc_env["OPCLI_TOKEN"] = token
    if env:
        proc_env.update(env)
    proc = subprocess.run(cmd, capture_output=True, text=True, input=stdin, env=proc_env)
    return Result(proc.returncode, proc.stdout, proc.stderr)


def _reachable() -> bool:
    if not BASE_URL or not TOKEN:
        return False
    try:
        return _run(["auth", "whoami"]).code == 0
    except Exception:
        return False


_LIVE = _reachable()


def pytest_collection_modifyitems(config, items):
    if _LIVE:
        return
    skip = pytest.mark.skip(reason="live OpenProject not configured (set OPCLI_BASE_URL + OPCLI_TOKEN)")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def op():
    """Callable that runs the CLI and returns a Result."""
    return _run


@pytest.fixture(scope="session")
def project(op):
    """A shared throw-away project for the session; deleted at the end.

    The creating admin is NOT automatically a project member, and OpenProject
    only lets *members* be assignees — so we add the current user with an
    assignable role to make assignment/available-assignee behaviour testable.
    """
    ident = f"op-cli-test-{RUN_ID}"
    res = op(["project", "create", "CLI Test " + RUN_ID, "--identifier", ident]).ok()
    proj = res.json
    for role in ("Project admin", "Member"):
        if op(["member", "add", "--project", ident, "--user", "me", "--role", role]).code == 0:
            break
    yield proj
    op(["project", "delete", ident, "-y"])


@pytest.fixture(scope="session")
def second_token():
    """Token of a second, non-admin user (jane.doe). Enables tests that need
    two actors (e.g. generating a notification). Skips when not provided."""
    tok = os.environ.get("OPCLI_SECOND_TOKEN")
    if not tok:
        pytest.skip("OPCLI_SECOND_TOKEN not set (needs a second user's token)")
    return tok


@pytest.fixture
def wp(op, project):
    """A fresh work package inside the shared project; cleaned up after the test."""
    res = op(["wp", "create", f"WP {uuid.uuid4().hex[:6]}", "--project", project["identifier"]]).ok()
    w = res.json
    yield w
    op(["wp", "delete", str(w["id"]), "-y"])
