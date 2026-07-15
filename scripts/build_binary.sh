#!/usr/bin/env bash
# Build a single self-contained `openproject` executable with PyInstaller.
#
# Produces dist/openproject (dist/openproject.exe on Windows) — one file, no Python needed on the
# target. Run once per OS/arch you want to ship (a frozen binary is
# platform-specific). CI (.github/workflows/release.yml) does this for
# linux/macOS/Windows on every tag.
set -euo pipefail
cd "$(dirname "$0")/.."

python -m pip install -q --upgrade pyinstaller

# keyring discovers its OS backends via entry points/metadata, which frozen apps
# drop by default — collect them explicitly, and add the platform backend.
EXTRA=()
case "$(uname -s)" in
  Linux)
    EXTRA+=(--collect-all secretstorage --collect-submodules jeepney
            --hidden-import keyring.backends.SecretService) ;;
  Darwin)
    EXTRA+=(--hidden-import keyring.backends.macOS) ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    EXTRA+=(--hidden-import keyring.backends.Windows) ;;
esac

pyinstaller --noconfirm --clean --onefile --name openproject \
  --paths src \
  --collect-all keyring \
  --hidden-import keyring.backends.chainer \
  --hidden-import keyring.backends.fail \
  "${EXTRA[@]}" \
  --distpath dist --workpath build/pyinstaller --specpath build \
  packaging/op_launcher.py

echo
echo "Built: $(ls -lh dist/openproject* | awk '{print $NF, "("$5")"}')"
echo "Try:   ./dist/openproject --help"
