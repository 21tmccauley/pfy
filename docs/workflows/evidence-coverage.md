# Evidence coverage

**Command:** `pfy evidence coverage` · [reference](../cli-reference.md#pfy-evidence-coverage)

Find the evidence sets that have **no validator** checking them — the compliance
gap where evidence is collected but never automatically validated. Optionally also
flag the reverse: validators in the catalog that aren't used by any evidence set.

```bash
pfy evidence coverage             # grouped tables
pfy evidence coverage --json      # structured report
```

## Why this isn't a simple "diff two lists"

You might expect to pull all evidence sets and all validators and diff them. The
Paramify API (v0.5.1) doesn't allow that, and understanding why explains the
command's shape:

- `GET /evidence` returns evidence sets — **with no validator field**.
- `GET /validators` returns the catalog — **with no evidence field**.
- The evidence↔validator link is set **write-only** via
  `POST /evidence/{id}/associate` (`subjectType: VALIDATOR`); there is **no read
  endpoint** for it.

The only place a validator appears tied to a specific evidence set in any `GET`
response is on its **artifacts**:

```
GET /evidence/{id}/artifacts  →  artifacts[].validators[]   (id, name, PASS/FAIL)
```

So "associated" is defined as **a validator has run against one of the evidence
set's artifacts**. Presence is the signal — a `FAIL` still counts as *associated*.

## How coverage is derived

1. `list_evidence()` — every evidence set (each carries `artifactCount`).
2. For each set: if `artifactCount == 0`, skip the fetch (nothing to observe);
   otherwise `list_artifacts(id)` and collect the validators seen.
3. `list_validators()` — the catalog, to find orphans (skipped with `--no-orphans`).

## Reading the buckets

| Bucket | Meaning | Action |
|---|---|---|
| **Covered** | ≥1 validator ran on an artifact | none |
| **No validator** | has artifacts, but none carry a validator | **the real gap** — attach a validator |
| **No artifacts yet** | nothing uploaded, so nothing to observe | can't tell — a validator may be attached but has never run |
| **Orphan validators** | catalog validator never seen on any evidence | unused — wire it up or retire it |

!!! warning "The one caveat"
    Because association is inferred from *runs*, an evidence set with a validator
    attached in the UI but **no artifacts yet** shows up under *No artifacts*, not
    *Covered*. That's deliberate — it's an honest "unknown," not a false "missing."
    If a real read-endpoint for the configured association ever ships, this command
    can swap the artifact walk for a direct lookup.

## JSON shape

```json
{
  "covered":        [{ "evidence_id": "...", "reference_id": "EVD-1", "name": "...", "artifact_count": 3, "validator_names": ["..."] }],
  "no_validator":   [{ "evidence_id": "...", "reference_id": "EVD-2", "artifact_count": 2 }],
  "no_artifacts":   [{ "evidence_id": "...", "reference_id": "EVD-3", "artifact_count": 0 }],
  "orphan_validators": [{ "validator_id": "...", "name": "...", "type": "ATTESTATION" }],
  "catalog_checked": true
}
```

```bash
# just the actionable gap, as reference ids
pfy evidence coverage --json | jq -r '.no_validator[].reference_id'
```
