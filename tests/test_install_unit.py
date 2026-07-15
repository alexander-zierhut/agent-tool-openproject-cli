"""Tests for `openproject install claude` (no network, no auth)."""

from __future__ import annotations

import os
import subprocess
import sys

from opcli.commands import install


def test_skill_md_is_valid_frontmatter():
    md = install.SKILL_MD
    assert md.startswith("---")
    assert "name: openproject" in md
    assert "description:" in md
    assert "openproject guide" in md  # points back at the in-tool guide
    assert len(md.splitlines()) < 500  # skill size guidance


def test_write_and_detect_skill(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert install.skill_installed() is False
    path = install.write_skill()
    assert path == tmp_path / ".claude" / "skills" / "openproject" / "SKILL.md"
    assert path.exists() and install.skill_installed() is True
    assert path.read_text().startswith("---")


def test_memory_hint_add_idempotent_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("# my notes\n")
    install.write_memory_hint()
    text = (tmp_path / ".claude" / "CLAUDE.md").read_text()
    assert "openproject-cli:start" in text and "# my notes" in text
    install.write_memory_hint()  # idempotent — no second copy
    assert (tmp_path / ".claude" / "CLAUDE.md").read_text().count("openproject-cli:start") == 1
    assert install._remove_memory_hint() is True
    after = (tmp_path / ".claude" / "CLAUDE.md").read_text()
    assert "openproject-cli" not in after and "# my notes" in after


def test_claude_available(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(install.shutil, "which", lambda _: None)
    assert install.claude_available() is False
    (tmp_path / ".claude").mkdir()
    assert install.claude_available() is True


def test_install_command_writes_skill(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "OPCLI_CONFIG_DIR": str(tmp_path / "cfg")}
    env.pop("OPCLI_TOKEN", None)
    env.pop("OPCLI_BASE_URL", None)
    proc = subprocess.run(
        [sys.executable, "-m", "opcli", "install", "claude", "--force"], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / ".claude" / "skills" / "openproject" / "SKILL.md").exists()


def test_install_print_needs_no_claude_or_auth(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "OPCLI_CONFIG_DIR": str(tmp_path / "cfg")}
    env.pop("OPCLI_TOKEN", None)
    proc = subprocess.run(
        [sys.executable, "-m", "opcli", "install", "claude", "--print"], capture_output=True, text=True, env=env
    )
    assert proc.returncode == 0
    assert proc.stdout.startswith("---")
    # --print must not write anything
    assert not (tmp_path / ".claude").exists()


def test_first_run_offer_installs_when_accepted(tmp_path):
    """Interactive first run with Claude Code present offers the skill; 'y' installs
    it, and the prompt only fires once."""
    import json
    import pty

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)  # makes claude_available() true
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    # preset format so the format prompt doesn't fire; claude not yet offered
    (cfg / "config.json").write_text('{"default_format":"json","claude_prompted":false,"profiles":{}}')
    env = {**os.environ, "HOME": str(home), "OPCLI_CONFIG_DIR": str(cfg)}
    env.pop("OPCLI_TOKEN", None)
    env.pop("OPCLI_BASE_URL", None)

    def run(answer: bytes):
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(sys.executable, [sys.executable, "-m", "opcli", "auth", "status"], env)
        os.write(fd, answer)
        out = b""
        try:
            while True:
                data = os.read(fd, 1024)
                if not data:
                    break
                out += data
        except OSError:
            pass
        os.waitpid(pid, 0)
        return out.decode(errors="replace")

    out = run(b"y\n")
    assert "Claude Code detected" in out
    assert (home / ".claude" / "skills" / "openproject" / "SKILL.md").exists()
    assert json.loads((cfg / "config.json").read_text())["claude_prompted"] is True

    # second run must NOT prompt again
    out2 = run(b"\n")
    assert "Claude Code detected" not in out2


def test_install_refuses_without_claude(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path), "OPCLI_CONFIG_DIR": str(tmp_path / "cfg")}
    env.pop("OPCLI_TOKEN", None)
    # empty HOME -> no ~/.claude; PATH without claude
    env["PATH"] = "/nonexistent-bin"
    proc = subprocess.run(
        [sys.executable, "-m", "opcli", "install", "claude"], capture_output=True, text=True, env=env
    )
    assert proc.returncode != 0
    assert "not detected" in (proc.stderr + proc.stdout).lower()
