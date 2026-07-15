"""PyInstaller entry point — a top-level script that boots the CLI.

PyInstaller freezes a *script*, not a package, so this thin launcher does the
absolute import PyInstaller needs (the package's own __main__ uses a relative
import that won't run as a top-level script).
"""

from opcli.cli import main

if __name__ == "__main__":
    main()
