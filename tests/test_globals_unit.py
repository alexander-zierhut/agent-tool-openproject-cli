"""The reserved global-flag namespace.

`cli.py::_pop_globals` strips a small set of flags from ANYWHERE on the command
line so they work before or after a subcommand. That power has a cost: those
flag names are **reserved**, and any command declaring one of its own can never
receive it — the popper eats it first, silently, with no error.

This actually shipped: `attach download --output f.pdf` had its `--output f.pdf`
swallowed as an output *format*, and the file quietly landed on its default name.
CI never caught it because the test only ever used the `-O` alias.

These tests are the guard. They are pure logic — no client, no network.
"""

from __future__ import annotations

from typer.main import get_command

from opcli.cli import _BOOL_FLAGS, _FIELDS_FLAGS, _FORMAT_FLAGS, _pop_globals, app

# The reserved namespace is EXACTLY what _pop_globals strips from argv — no more.
# Derived from the real tuples, so if someone widens the popper (the Drone port
# plans to pop --profile/--no-color too), this guard widens with it automatically.
#
# Deliberately NOT reserved: --version/-V, --profile/-p, --no-color. Those are
# ordinary root options that Click never removes from a subcommand's argv, so a
# subcommand may legitimately shadow them — verified: `wp list --version "Sprint 3"`
# filters by version and `raw get x -p k=v` passes a param, both correctly.
# Reserving them would have flagged four working commands as broken.
RESERVED = set(_FORMAT_FLAGS) | set(_FIELDS_FLAGS) | set(_BOOL_FLAGS)


def _walk(cmd, path: str = ""):
    """Yield (command_path, command) for every leaf in the tree.

    Duck-typed on purpose: Typer vendors Click privately (`typer._click`) and has
    moved it before, so `isinstance(x, click.Group)` is a liability. cli.py's own
    `_context_default_map` walks the tree the same way.
    """
    subs = getattr(cmd, "commands", None)
    if subs:
        for name, sub in subs.items():
            yield from _walk(sub, f"{path} {name}".strip())
    else:
        yield path, cmd


def _leaf_commands():
    return list(_walk(get_command(app)))


def test_the_tree_actually_has_commands():
    # Guard the guard: if introspection breaks, the reservation test below would
    # pass vacuously and we would learn nothing.
    leaves = _leaf_commands()
    assert len(leaves) > 20, f"expected the full command tree, walked only {len(leaves)}"


def test_no_command_declares_a_reserved_global():
    """No command may declare an option whose name is a reserved global.

    One test, not one-per-command: this is a single rule, and parametrising it
    over ~90 commands would add ~90 to the suite count while asserting the same
    thing. The message names every offender, so a failure is just as actionable.
    """
    offenders = []
    for path, cmd in _leaf_commands():
        if not path:
            continue  # the root callback legitimately *defines* the globals
        for param in cmd.params:
            if getattr(param, "param_type_name", "") != "option":
                continue
            clashes = sorted(set(param.opts) & RESERVED)
            if clashes:
                offenders.append(f"  `openproject {path}` declares {clashes}")

    assert not offenders, (
        "These options can never be received — _pop_globals strips the reserved "
        "globals from anywhere on the line before Click parses them:\n"
        + "\n".join(offenders)
        + "\n\nRename the local option (e.g. --output -> --out), or stop popping the flag."
    )


def test_attach_download_out_is_not_swallowed():
    """Regression: the exact call that used to lose its filename."""
    fmt, fields, bools, argv = _pop_globals(
        ["attach", "download", "1", "--out", "f.pdf"]
    )
    assert fmt is None, "--out must not be read as an output format"
    assert argv == ["attach", "download", "1", "--out", "f.pdf"], "--out must survive intact"


def test_output_is_still_a_global_format_flag():
    """The reservation is real: --output IS the format flag, everywhere."""
    fmt, _fields, _bools, argv = _pop_globals(["wp", "list", "--output", "table"])
    assert fmt == "table"
    assert argv == ["wp", "list"]
