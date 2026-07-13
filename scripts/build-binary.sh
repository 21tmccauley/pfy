#!/usr/bin/env bash
# Build a self-contained `pfy` as a PyInstaller onedir bundle.
#
# The bundle carries the interpreter AND every dependency — including the private
# `paramify-sdk` and the compiled `pydantic-core` — so the machine that installs
# it needs neither Python nor GitHub auth. Because pydantic-core is a native
# wheel, the artifact is OS+arch specific: run this once per target in CI.
#
# onedir (not onefile) on purpose: a onefile binary re-extracts its whole payload
# to a temp dir AND macOS re-verifies those freshly-written, unsigned Mach-O files
# on *every* launch (~5s startup). onedir unpacks once, to disk, at install time,
# so startup is ~10x faster. The trade-off is the artifact is a directory.
#
# Usage:  scripts/build-binary.sh
# Output: dist/pfy/                       (the bundle dir: `pfy` + _internal/)
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
  --onedir \
  --name pfy \
  --paths src \
  --collect-submodules pfy \
  --collect-submodules paramify_sdk \
  --collect-submodules pydantic \
  --collect-submodules pydantic_core \
  --collect-submodules mcp \
  src/pfy/__main__.py

# Smoke-test the frozen binary before we ship it — proves the interpreter,
# pydantic-core, and the bundled SDK all import inside the onedir bundle. The
# executable lives at dist/pfy/pfy (onedir), with its libs in dist/pfy/_internal.
./dist/pfy/pfy --help >/dev/null

# Tar the whole bundle dir; Homebrew strips the single leading `pfy/` on unpack.
tar -C dist -czf "dist/${asset}.tar.gz" pfy
shasum -a 256 "dist/${asset}.tar.gz" | tee "dist/${asset}.tar.gz.sha256"
echo ">> done: dist/${asset}.tar.gz"
