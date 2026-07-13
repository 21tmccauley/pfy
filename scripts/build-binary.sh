#!/usr/bin/env bash
# Build a single-file, self-contained `pfy` binary with PyInstaller.
#
# The binary bundles the interpreter AND every dependency — including the
# private `paramify-sdk` and the compiled `pydantic-core` — so the machine that
# installs it needs neither Python nor GitHub auth. Because pydantic-core is a
# native wheel, the artifact is OS+arch specific: run this once per target in CI.
#
# Usage:  scripts/build-binary.sh
# Output: dist/pfy                        (the executable)
#         dist/pfy-<os>-<arch>.tar.gz     (the release asset + its .sha256)
set -euo pipefail
cd "$(dirname "$0")/.."

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "$os" in
  darwin) os="macos" ;;
  linux)  os="linux" ;;
esac
arch="$(uname -m)"   # arm64 on Apple Silicon, x86_64 on Intel/most Linux
asset="pfy-${os}-${arch}"

echo ">> building ${asset}"
rm -rf build dist "${asset}.tar.gz"

pyinstaller \
  --onefile \
  --name pfy \
  --paths src \
  --collect-submodules pfy \
  --collect-submodules paramify_sdk \
  --collect-submodules pydantic \
  --collect-submodules pydantic_core \
  src/pfy/__main__.py

# Smoke-test the frozen binary before we ship it — proves the interpreter,
# pydantic-core, and the bundled SDK all import inside the onefile bundle.
./dist/pfy --help >/dev/null

tar -C dist -czf "dist/${asset}.tar.gz" pfy
shasum -a 256 "dist/${asset}.tar.gz" | tee "dist/${asset}.tar.gz.sha256"
echo ">> done: dist/${asset}.tar.gz"
