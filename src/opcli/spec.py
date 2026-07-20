"""This tool's identity, and the shared services derived from it.

Everything tool-specific about the shared chassis (`agentcli`) is these two
strings. The config directory, the keyring service name and every `OPCLI_*`
environment variable follow from them — defined once, here, so nothing can drift.

`credentials` is a module-level instance on purpose: call sites read
``credentials.get_token(profile)``, exactly as they did when it was a module.
"""

from __future__ import annotations

from agentcli import AppSpec, Credentials

SPEC = AppSpec(
    name="op-cli",
    env_prefix="OPCLI",
    repo="alexander-zierhut/agent-tool-openproject-cli",
)

credentials = Credentials(SPEC)
