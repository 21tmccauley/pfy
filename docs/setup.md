# Setup

## Install

Most people just want the CLI:

```bash
brew install paramify/tap/pfy
pfy --help
```

That's a self-contained binary (interpreter + all dependencies, including the
private SDK, baked in) — no Python and no repo access required. Upgrade later with
`brew upgrade pfy`.

### From source (to develop pfy)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # needs git auth for the private SDK (gh auth setup-git)
pfy --help
```

`paramify-sdk` is private and pinned by a git tag. If `pip install` can't reach it,
install it from a local checkout first, then install pfy without deps:

```bash
pip install -e ../paramify-sdk
pip install -e . --no-deps
```

## Authenticate

`pfy` reads its settings from the environment (or a git-ignored `.env`). Copy the
template and fill it in:

```bash
cp .env.example .env
```

| Variable | Required | Notes |
|---|---|---|
| `PARAMIFY_API_KEY` | yes | Your Paramify API token. |
| `PARAMIFY_URL` | no | Defaults to **stage** (`https://stage.paramify.com/api/v0`). |
| `PROGRAM_ID` | no | Default program/project id, so you can omit `--program-id`. |
| `NVD_API_KEY` | no | Raises the NVD rate limit for `vuln` commands. |

!!! warning "Stage is the default"
    `pfy` defaults `PARAMIFY_URL` to **stage**. A stage token against a prod URL
    (or vice-versa) returns `401`. Set `PARAMIFY_URL` explicitly when you mean prod.

## Verify

```bash
pfy programs list          # smallest authenticated round-trip
```

If that returns your programs, auth and connectivity are good. From there, see
[Concepts](concepts.md) for how commands compose, or jump to a
[workflow](workflows/evidence-coverage.md).
