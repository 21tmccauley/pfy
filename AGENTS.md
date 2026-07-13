# pfy — guide for AI agents

`pfy` is the Paramify FDE CLI: porcelain workflows + plumbing primitives over the
`paramify-sdk`. This file tells an agent how to drive it. Humans: see `README.md`.

## Talk to it two ways — same core underneath

1. **Shell out** to the CLI (`pfy …`). Best for one-off steps and composing with
   other tools.
2. **MCP** — run `pfy mcp` (stdio) and call its tools. Best when you're an
   MCP-capable agent and want typed tools instead of parsing text. Requires the
   optional extra: `pip install 'pfy[mcp]'`.

Both call the *same* service functions, so a workflow behaves identically either way.

## Auth (both modes)

Set in the environment (or a `.env` in the working dir):

- `PARAMIFY_API_KEY` — required.
- `PARAMIFY_URL` — defaults to **stage** (`https://stage.paramify.com/api/v0`). A
  stage token against a prod URL (or vice-versa) returns 401. Set it to
  `https://app.paramify.com/api/v0` for prod.

Smallest authenticated check: `pfy programs list`.

## Output contract (the part that makes it scriptable)

- **Get JSON**: pass `--json`, **or** set `PFY_JSON=1` once in the environment to
  make every command emit JSON. Do this — parse JSON, never the human tables.
- Human (non-JSON) output is tab-separated, so `cut`/`awk` also work.
- **Exit codes**: `0` = success (*including* "nothing to report" — e.g. no failing
  validators), `1` = a real error (auth/config/API), `2` = a usage error (bad/
  missing flags). Do not treat exit `1` on an empty result as "the tool broke."
- Errors print `Error: …` (+ a `Hint:`) to **stderr**, never a traceback.

## When to use what

| Tier | Use it for | Examples |
|---|---|---|
| **Porcelain** (`Workflows`) | a whole job done well | `pfy vuln adjust-program`, `pfy validator triage` |
| **Plumbing** (`Plumbing`) | one resource / one endpoint, JSON-first | `pfy issues list`, `pfy programs get`, `pfy evidence …` |
| **Escape hatch** | any endpoint with no typed command yet | `pfy api GET evidence --param projectId=P1` |

Prefer a porcelain command when one fits. Otherwise **compose** plumbing +
`pfy api` in a shell script rather than expecting a bespoke command to exist —
that's the intended way to build a workflow nobody pre-built.

## Validator triage (the flagship workflow)

```bash
pfy validator list-failing --json                 # cheap survey: what's failing
pfy validator triage --json --compact             # full analysis, most-severe first
pfy validator triage --json --compact --limit 5   # cap the work
pfy validator triage --json --evidence-ref EVD-KSI-IAM-01   # scope to one evidence set
```

- **Always pass `--compact`** unless you need the long `what_it_checks` narrative —
  it strips ~600 chars/result you're otherwise paying for.
- Each result has: `classification` (`compliance_gap` = evidence really regressed;
  `brittle_validator` = the regex/rule no longer matches the artifact's shape;
  `data_issue` = wrong file / not evaluable), `severity`, `why_failing`,
  `what_changed` (vs the last passing artifact), and `remediation`.
- Offline (no API), triage/replay/diff a local example:
  `pfy validator triage --validator v.json --failing f.json [--passing p.json]`.

## MCP tools (`pfy mcp`)

Every tool calls the same service function as the equivalent CLI command and
returns the identical shapes (coerced exactly as `--json`), so the two faces
can't drift. All are read-only except `vuln_adjust_program`, and that defaults
to a dry run.

**Validators**
- `validator_list_failing(evidence_refs?)` → failing validators (the cheap survey).
- `validator_triage(evidence_refs?, limit?, compact=true)` → full triage results,
  most-severe first.

**Survey the compliance state (read-only)**
- `programs_list()` → programs (id + name).
- `issues_list(program_id?, poam_ids?, cve_ids?, kev?, has_cves?)` → issues with
  inline deviations. Needs a scope: `program_id` (or the `PROGRAM_ID` setting),
  `poam_ids`, or `cve_ids`.
- `issues_get(issue_id)` → one issue by id.
- `evidence_coverage(evidence_refs?, orphans=true)` → evidence sets with no
  validator observed on any artifact (+ optional orphan validators).
- `vuln_score(cve_ids)` → max NVD CVSS base score across the CVEs.

**Vuln workflow (write-capable)**
- `vuln_adjust_program(program_id?, write=false)` → score a program's CVE-bearing
  issues and plan their deviations. `write=false` (default) is a **dry run** —
  actions come back as `would-create` / `would-update` / `unchanged` and nothing
  is sent to Paramify. Pass `write=true` to actually create/update deviations.

Register the server with your agent host as command `pfy`, args `["mcp"]`, passing
`PARAMIFY_API_KEY` / `PARAMIFY_URL` in its environment.
