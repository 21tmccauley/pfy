# Contributing

## Docs are generated from the code — keep them that way

The [CLI reference](docs/cli-reference.md) is **generated** from the Typer app by
`scripts/gen-docs.sh`. The command tree is the single source of truth, so the only
doc work a new command needs is the same text you'd write for `--help`.

### Adding or changing a command — the checklist

1. **Write a docstring** on the command function. The first line is the summary
   shown in listings; the rest becomes the command's description in `--help` and in
   the generated reference.
2. **Add `help=`** to every `typer.Option` / `typer.Argument`. That text is the
   only per-option documentation there is.
3. **Regenerate the reference** and commit it:
   ```bash
   ./scripts/gen-docs.sh        # inside the venv
   ```
4. **Document the *why*, not just the *what*.** `--help` explains what a flag does;
   it can't explain when or why to reach for the command. If the command embodies a
   judgment call (an API constraint, a non-obvious default, a workflow), add or
   update a page under `docs/workflows/` and link it from the nav in `mkdocs.yml`.

!!! danger "Never hand-edit `docs/cli-reference.md`"
    It is overwritten on every regeneration, and CI fails if the committed copy
    doesn't match a fresh generate (see below). Edit the docstring / `help=`
    instead.

### What CI enforces

`.github/workflows/docs.yml` regenerates the reference and fails if it differs from
the committed file — so a command that lacks a docstring, or a stale reference, is
caught automatically. It also runs `mkdocs build --strict` (catches broken links
and bad nav). On `main`, the site is built and published to GitHub Pages.

## Build the docs site locally

```bash
pip install -e ".[docs]"
mkdocs serve                 # live-reload preview at http://127.0.0.1:8000
mkdocs build --strict        # what CI runs
```
