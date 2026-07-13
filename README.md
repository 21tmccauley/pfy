# pfy

The Paramify FDE CLI. One install, one auth surface, and every headless workflow
we've built behind a single discoverable command — instead of a drawer of
disjointed scripts.

## Install

```bash
brew install paramify/tap/pfy
```

A self-contained binary — no Python, no repo access needed. Then set up auth
(`cp .env.example .env`, or export `PARAMIFY_API_KEY`) per [setup](docs/setup.md),
and check it with `pfy programs list`. To hack on pfy instead, see [Develop](#develop).
Cutting a release is documented in [RELEASING.md](RELEASING.md).

`pfy` is the **`app/` delivery** at the top of the FDE stack: it depends on the
pinned [`paramify-sdk`](https://github.com/paramify/paramify-sdk) for transport,
and each workflow's real logic lives in a pure `core/` capability. The CLI is a
convenience surface over those capabilities, not their home.

## Two tiers of command (+ an escape hatch)

Modeled on `git`'s porcelain/plumbing split, and mirroring the SDK's own
typed-method / `request()` layering:

| Tier | Example | What it is |
|---|---|---|
| **Porcelain** — opinionated workflow | `pfy vuln adjust-program` | multi-step, one job done well |
| **Plumbing** — decomposed primitive | `pfy issues list`, `pfy programs get` | one resource/one endpoint, JSON-first, scriptable |
| **Escape hatch** — raw request | `pfy api GET evidence --param projectId=…` | any endpoint, even ones with no typed primitive yet |

The plumbing tier is what lets you (or an AI) *compose* a workflow that nobody
pre-built. When a composed pipeline recurs, promote it to a porcelain command —
the same discipline as escape-hatch-call → typed SDK method.

```bash
# porcelain: the whole job, one shot
pfy vuln adjust-program --program-id PRJ-1 --post-deviations

# plumbing: compose a variant yourself
pfy issues list --program-id PRJ-1 --kev --json | jq -r '.[].id'

# escape hatch: reach an un-wrapped endpoint
pfy api GET evidence --param projectId=PRJ-1
```

## Output contract (why scripting works)

Every command that returns data emits through one place (`app/output.py`):
human-readable, tab-separated by default; add `--json` (or set `PFY_JSON=1` once)
for machine-readable output with stable field names. Bodies for writes can be
piped in via `--stdin`. That single contract is what makes the plumbing tier
composable.

## For AI agents

pfy is built to be driven by an agent, two ways over the same core:

- **Shell out** to the CLI and parse `--json` (or `PFY_JSON=1`).
- **MCP** — `pfy mcp` serves the same workflows as MCP tools over stdio
  (`pip install 'pfy[mcp]'`). Register it with your agent host as command `pfy`,
  args `["mcp"]`.

Agent-facing usage — the output/exit-code contract and when to use each tier —
lives in [`AGENTS.md`](AGENTS.md) (Claude Code reads it via `CLAUDE.md`).

## Layout

```
src/pfy/
├── core/                     # pure capabilities — logic + typed contracts, no I/O
│   ├── vuln/                 #   CVSS selection, scoring seam, deviation planning
│   └── validator/            #   failing-validator triage contract (extraction in progress)
└── app/                      # everything that touches the outside world
    ├── output.py             #   the one JSON/text output contract
    ├── settings.py           #   pydantic-settings (Paramify defaults to STAGE)
    ├── clients/              #   paramify-sdk facade + NVD client
    ├── services.py           #   orchestration (porcelain implementations)
    └── cli/
        ├── main.py           #   Typer root; mounts command groups
        └── commands/         #   one module per group (plumbing + porcelain)
```

The one hard rule, enforced in CI by `import-linter`: **`core` never imports
`app`.** That keeps each capability liftable out of the CLI later.

## Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # needs git auth for the private SDK (gh auth setup-git)
ruff check . && mypy && lint-imports && pytest -q
pfy --help
```

`paramify-sdk` is private; if `pip install` can't reach it, install it from a
local checkout first (`pip install -e ../paramify-sdk`) then `pip install -e . --no-deps`.
