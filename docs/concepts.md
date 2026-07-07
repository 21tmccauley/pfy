# Concepts

Two ideas explain the whole CLI: a **two-tier command model** and a single
**output contract**. Everything else follows from them.

## Two tiers of command (+ an escape hatch)

Modeled on `git`'s porcelain/plumbing split, and mirroring the SDK's own
typed-method / `request()` layering:

| Tier | Example | What it is |
|---|---|---|
| **Porcelain** — opinionated workflow | `pfy vuln adjust-program` | multi-step, one job done well |
| **Plumbing** — decomposed primitive | `pfy issues list`, `pfy programs get` | one resource / one endpoint, JSON-first, scriptable |
| **Escape hatch** — raw request | `pfy api GET evidence --param projectId=…` | any endpoint, even ones with no typed primitive yet |

The plumbing tier is what lets you (or an AI) *compose* a workflow that nobody
pre-built. When a composed pipeline recurs, promote it to a porcelain command —
the same discipline as escape-hatch call → typed SDK method.

```bash
# escape hatch → compose with plumbing → promote to porcelain, as patterns prove out
pfy api GET evidence --param projectId=PRJ-1        # 1. reach a raw endpoint
pfy evidence coverage --json | jq '.no_validator'   # 2. a composed, repeatable view
```

## The output contract

Every command that returns data emits through one place (`app/output.py`):

- **Human-readable by default** — tab-separated rows (plumbing) or grouped tables
  (porcelain), so output stays `awk`/`cut`-friendly.
- **`--json`** — stable field names for machine consumption.
- **`--stdin`** — write commands can read a JSON body from stdin.

```bash
pfy issues list --program-id PRJ-1 --json | jq -r '.[].id'
```

That single contract is what makes the plumbing tier composable. When you script
against `pfy`, script against `--json`; the human format is free to be prettier.

## The layering underneath

```
src/pfy/
├── core/     # pure capabilities — logic + typed contracts, no I/O
└── app/      # everything that touches the outside world (SDK/NVD clients, CLI)
```

The one hard rule, enforced in CI by `import-linter`: **`core` never imports
`app`.** That keeps each capability liftable out of the CLI later — into a
schedule, the platform, or an AI tool — without dragging transport or Typer along.

!!! note "Why this matters for docs"
    Because a command is a thin Typer surface over a `core` capability, its
    docstring and option `help=` text fully describe the *interface*. That's why
    the [CLI reference](cli-reference.md) can be generated from the code. What the
    generated reference *can't* capture — the *why* and *when* — lives in the
    [workflow guides](workflows/evidence-coverage.md).
