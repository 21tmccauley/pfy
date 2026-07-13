# Releasing pfy

`pfy` ships as a self-contained binary via Homebrew. A tag push builds one binary
per macOS arch, attaches them to a GitHub Release, and bumps the tap formula.
End users run `brew install paramify/tap/pfy` — no Python, no GitHub auth.

Why a bundled binary and not a normal `pip`/Homebrew-Python formula: `paramify-sdk`
is a private git dependency, so it can't be resolved on a user's machine. We bake
it into the binary in CI (where a token exists) instead. `pydantic-core` is a
native wheel, so the artifact is arch-specific — hence one build per arch.

## One-time setup

1. **Create the tap repo** `paramify/homebrew-tap` (public). A tap is just a repo
   named `homebrew-<name>`; formulae live in `Formula/`. The release workflow
   writes `Formula/pfy.rb` for you, so an empty repo with a README is enough.

2. **Add repository secrets** to `paramify/pfy`:
   | Secret | What | Scope |
   |---|---|---|
   | `SDK_TOKEN` | PAT/read token for `paramify/paramify-sdk` | so CI can `pip install` the private dep |
   | `HOMEBREW_TAP_TOKEN` | PAT with write access to `paramify/homebrew-tap` | so CI can commit the bumped formula |

   (`GITHUB_TOKEN` is provided automatically for this repo's own release + uploads.)

3. **Make releases public.** For `brew install` to work without a token, the `pfy`
   repo's Releases must be publicly downloadable. If `pfy` must stay private,
   switch the formula to a private-release download strategy and have users set
   `HOMEBREW_GITHUB_API_TOKEN` — see the note at the bottom.

## Cut a release

```bash
# 1. Bump the version in pyproject.toml to match the tag you're about to push.
# 2. Tag and push:
git tag v0.1.0
git push origin v0.1.0
```

The `release` workflow then:
1. creates the GitHub Release,
2. builds `pfy-macos-arm64.tar.gz` (macos-14) and `pfy-macos-x86_64.tar.gz`
   (macos-13) via `scripts/build-binary.sh` and uploads them,
3. renders `packaging/homebrew/pfy.rb` with the version + checksums and commits it
   to the tap.

Users upgrade with `brew update && brew upgrade pfy`.

## Build locally (to debug the binary)

```bash
pip install -e ".[build]"
scripts/build-binary.sh            # → dist/pfy  +  dist/pfy-<os>-<arch>.tar.gz
./dist/pfy --help
```

The script smoke-tests the frozen binary (`pfy --help`) before packaging, so a
broken bundle fails the build rather than shipping.

## Adding Linux

The build script already labels `linux` artifacts. Add an `ubuntu-latest` entry to
the `build` matrix and an `on_linux do ... end` block to the formula. Note the
binary is glibc-specific; build on the oldest glibc you need to support.

## If pfy itself must stay private

Public releases are what make `brew install` tokenless. To keep `pfy` private:
replace the formula's `url` with a `GitHubPrivateRepositoryReleaseDownloadStrategy`
(a small Ruby strategy in the tap), keep the tap private, and have each user set a
`HOMEBREW_GITHUB_API_TOKEN` with read access. The binary itself never needs the SDK
token — only the download does.
