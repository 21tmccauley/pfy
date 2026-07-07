# pfy — the Paramify FDE CLI

One install, one auth surface, and every headless workflow the FDE team has built
behind a single discoverable command — instead of a drawer of disjointed scripts.

`pfy` sits at the top of the FDE stack: it depends on the pinned
[`paramify-sdk`](https://github.com/paramify/paramify-sdk) for transport, and each
workflow's real logic lives in a pure `core/` capability. The CLI is a convenience
surface over those capabilities, not their home.

## Where to start

<div class="grid cards" markdown>

- :material-rocket-launch: **[Setup](setup.md)** — install, authenticate, point at
  stage vs prod.
- :material-lightbulb-on: **[Concepts](concepts.md)** — the porcelain/plumbing
  split and the output contract that make commands composable.
- :material-checkbox-marked-circle: **[Workflows](workflows/evidence-coverage.md)** —
  the "why and when" behind each opinionated command.
- :material-console: **[CLI reference](cli-reference.md)** — every command and
  option, generated from the code.

</div>

## The 30-second tour

```bash
# porcelain: the whole job, one shot
pfy vuln adjust-program --program-id PRJ-1 --post-deviations

# plumbing: compose a variant yourself
pfy issues list --program-id PRJ-1 --kev --json | jq -r '.[].id'

# escape hatch: reach an un-wrapped endpoint
pfy api GET evidence --param projectId=PRJ-1
```

Every data-returning command prints human-readable text by default and stable JSON
with `--json`, so the same command works at a glance or in a pipeline. See
[Concepts](concepts.md) for why that matters.

!!! info "These docs stay in sync with the code"
    The [CLI reference](cli-reference.md) is generated from the Typer app itself —
    every command's docstring and each option's `help=` text. Adding a command
    documents it automatically. See [CONTRIBUTING](https://github.com/paramify/pfy/blob/main/CONTRIBUTING.md).
