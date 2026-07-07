"""``pfy validator`` — triage failing Paramify validators.

Plumbing: ``list-failing`` (API walk), ``replay`` / ``diff`` (pure, local files —
no API). Porcelain: ``triage`` (live API by default; ``--validator``/``--failing``
for an offline example). The deterministic engine lives in ``core.validator``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from pfy.app import output, validator_service
from pfy.app.cli.context import Context
from pfy.core.validator.diff import diff as run_diff
from pfy.core.validator.models import Diff, RegexReplay, TriageResult
from pfy.core.validator.replay import replay as run_replay

app = typer.Typer(no_args_is_help=True)

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _read(path: Path) -> tuple[str, Any]:
    raw = path.read_text()
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError:
        return raw, None


@app.command("list-failing")
def list_failing(
    ctx: typer.Context,
    evidence_ref: list[str] | None = typer.Option(
        None, "--evidence-ref", help="Limit to evidence referenceId (repeatable)"
    ),
    json_out: output.JSONOption = False,
) -> None:
    """List validators currently failing on their newest artifact (live API)."""
    c: Context = ctx.obj
    records = validator_service.find_failing(c.paramify, evidence_refs=evidence_ref or None)
    rows = [
        {
            "validator": r.validator_name,
            "validatorId": r.validator_id,
            "evidence": r.evidence.get("referenceId") or r.evidence.get("name"),
            "baseline": "yes" if r.last_passing else "no",
        }
        for r in records
    ]
    output.emit_rows(rows, ["validator", "validatorId", "evidence", "baseline"], as_json=json_out)


@app.command("replay")
def replay(
    validator: Path = typer.Option(..., "--validator", help="Validator definition JSON file"),
    failing: Path = typer.Option(..., "--failing", help="Failing artifact file"),
    json_out: output.JSONOption = False,
) -> None:
    """Replay a validator's regex/rules against a failing artifact (local files, no API)."""
    val = json.loads(validator.read_text())
    raw, _ = _read(failing)
    output.emit(run_replay(val, raw), as_json=json_out, human=_replay_human)


@app.command("diff")
def diff(
    failing: Path = typer.Option(..., "--failing", help="Failing artifact JSON file"),
    passing: Path = typer.Option(..., "--passing", help="Last-passing artifact JSON file"),
    json_out: output.JSONOption = False,
) -> None:
    """Diff a failing artifact against the last-passing one (local JSON files, no API)."""
    _, fail_content = _read(failing)
    _, pass_content = _read(passing)
    output.emit(run_diff(fail_content, pass_content), as_json=json_out, human=_diff_human)


@app.command("triage")
def triage(
    ctx: typer.Context,
    validator: Path | None = typer.Option(None, "--validator", help="[offline] validator JSON"),
    failing: Path | None = typer.Option(None, "--failing", help="[offline] failing artifact"),
    passing: Path | None = typer.Option(None, "--passing", help="[offline] last-passing artifact"),
    evidence_name: str | None = typer.Option(
        None, "--evidence-name", help="[offline] evidence name"
    ),
    evidence_ref: list[str] | None = typer.Option(
        None, "--evidence-ref", help="[live] limit to evidence referenceId (repeatable)"
    ),
    limit: int | None = typer.Option(None, "--limit", help="[live] cap the number analyzed"),
    json_out: output.JSONOption = False,
) -> None:
    """Triage failing validators: find -> bundle -> baseline analysis.

    Live API by default; pass --validator and --failing to triage a local example.
    """
    c: Context = ctx.obj
    if validator or failing:
        if not (validator and failing):
            raise typer.BadParameter("offline mode needs both --validator and --failing")
        results = [validator_service.triage_files(validator, failing, passing, evidence_name)]
    else:
        results = validator_service.triage_live(
            c.paramify, c.http, evidence_refs=evidence_ref or None, limit=limit
        )
    results.sort(key=lambda t: _SEVERITY_ORDER.get(t.severity, 9))
    output.emit(results, as_json=json_out, human=_triage_human)
    raise typer.Exit(0 if results else 1)


def _replay_human(r: RegexReplay) -> None:
    if not r.available:
        typer.echo(r.note or "no regex to replay")
        return
    if r.error:
        typer.echo(f"regex error: {r.error}", err=True)
        return
    typer.echo(f"matches: {r.matches_found}")
    for rr in r.rule_results:
        verdict = {True: "PASS", False: "FAIL", None: "?"}[rr.passed]
        typer.echo(f"  rule {rr.rule_index}\t{verdict}\t{rr.explanation}")


def _diff_human(d: Diff) -> None:
    if not d.available:
        typer.echo(d.reason or "no diff available", err=True)
        return
    if not d.changes:
        typer.echo("no changes")
        return
    for c in d.changes:
        delta = "" if c.delta is None else f"\t({'+' if c.delta >= 0 else ''}{c.delta:g})"
        typer.echo(f"{c.path}\t{c.previous} → {c.current}{delta}")


def _triage_human(results: list[TriageResult]) -> None:
    for t in results:
        name = t.validator_name or t.validator_id
        typer.echo(f"[{t.severity.upper()}] {name} ({t.classification})\t{t.evidence_name or ''}")
        typer.echo(f"  why:      {t.why_failing}")
        if t.what_changed:
            typer.echo(f"  changed:  {t.what_changed}")
        typer.echo(f"  fix:      {t.remediation}")
