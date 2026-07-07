# Validator triage

**Command group:** `pfy validator` · [reference](../cli-reference.md#pfy-validator)

Triage validators that are **currently failing** on their newest artifact:
find them, reconstruct what changed, and classify *why* — so you know whether the
evidence really regressed or the validator itself is brittle.

The deterministic engine lives in `core.validator` (replay, diff, detect, triage),
which means every step below is reproducible and testable without the API.

## Commands

| Command | Live API? | Use it to |
|---|---|---|
| `pfy validator list-failing` | yes | list validators failing on their newest artifact |
| `pfy validator triage` | yes (default) | full workflow: find → bundle → baseline analysis |
| `pfy validator replay` | no (local files) | re-run a validator's regex/rules against an artifact |
| `pfy validator diff` | no (local files) | diff a failing artifact against the last-passing one |

```bash
# what's failing right now
pfy validator list-failing --json

# triage everything failing, worst first
pfy validator triage

# triage a hand-collected example offline (no API)
pfy validator triage --validator val.json --failing fail.json --passing pass.json
```

## How a failure is classified

For each failing validator, `triage` assembles a self-contained bundle (the
validator definition, the failing artifact, and the last-passing one if there is a
baseline) and produces a classification:

| Classification | Meaning |
|---|---|
| `compliance_gap` | the evidence really is non-compliant |
| `brittle_validator` | the regex/rule doesn't match the real artifact shape |
| `data_issue` | wrong file / not JSON / can't replay |

`triage` exits non-zero when nothing is failing, so it composes in a check.

!!! tip "Offline reproduction"
    `replay` and `diff` take local files and never touch the API — ideal for
    reproducing a customer's failure from a saved artifact, or for building a
    regression fixture before changing a validator.
