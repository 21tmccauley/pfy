"""``pfy evidence`` — evidence sets and their validator coverage.

Porcelain: ``coverage`` composes ``GET evidence`` + per-set artifacts + the
validator catalog into a gap report — which evidence sets have no validator
observed on any artifact, and (optionally) which catalog validators aren't used
by any evidence set. The deterministic bucketing lives in ``core.evidence``.
"""

from __future__ import annotations

import typer

from pfy.app import evidence_service, output
from pfy.app.cli.context import Context
from pfy.core.evidence.models import CoverageReport, EvidenceCoverage

app = typer.Typer(no_args_is_help=True)


@app.command("coverage")
def coverage(
    ctx: typer.Context,
    evidence_ref: list[str] | None = typer.Option(
        None, "--evidence-ref", help="Limit to evidence referenceId (repeatable)"
    ),
    orphans: bool = typer.Option(
        True,
        "--orphans/--no-orphans",
        help="Also flag catalog validators not used by any evidence set",
    ),
    json_out: output.JSONOption = False,
) -> None:
    """Evidence sets with no associated validator (+ optional orphan validators).

    A validator counts as associated when it has run against one of the evidence
    set's artifacts — the only association the API exposes. Evidence with no
    artifacts yet is reported separately (a validator may be attached but unrun).
    """
    c: Context = ctx.obj
    report = evidence_service.find_validator_coverage(
        c.paramify, evidence_refs=evidence_ref or None, check_catalog=orphans
    )
    output.emit(report, as_json=json_out, human=_human)


_EVIDENCE_COLUMNS = ["reference", "name", "artifacts"]
_EVIDENCE_HEADERS = ["REFERENCE", "NAME", "ARTIFACTS"]


def _evidence_rows(items: list[EvidenceCoverage]) -> list[dict[str, object]]:
    return [
        {
            "reference": cov.reference_id or cov.evidence_id,
            "name": cov.name or "",
            "artifacts": cov.artifact_count,
        }
        for cov in items
    ]


def _section(title: str, items: list[EvidenceCoverage]) -> None:
    if not items:
        return
    typer.echo(f"\n{title} ({len(items)})")
    output.grid(_evidence_rows(items), _EVIDENCE_COLUMNS, _EVIDENCE_HEADERS, indent="  ")


def _human(report: CoverageReport) -> None:
    summary = [
        {"bucket": "Covered (validator seen on an artifact)", "count": len(report.covered)},
        {"bucket": "No validator (has artifacts)", "count": len(report.no_validator)},
        {"bucket": "No artifacts yet (status unknown)", "count": len(report.no_artifacts)},
    ]
    if report.catalog_checked:
        summary.append(
            {"bucket": "Orphan validators (unused)", "count": len(report.orphan_validators)}
        )
    typer.echo("SUMMARY")
    output.grid(summary, ["bucket", "count"], ["BUCKET", "COUNT"], indent="  ")

    _section("Evidence sets WITH artifacts but NO validator", report.no_validator)
    _section("Evidence sets with NO artifacts yet", report.no_artifacts)

    if report.catalog_checked and report.orphan_validators:
        typer.echo(f"\nValidators not used by any evidence set ({len(report.orphan_validators)})")
        rows = [
            {"id": v.validator_id, "name": v.name or "", "type": v.type or ""}
            for v in report.orphan_validators
        ]
        output.grid(rows, ["id", "name", "type"], ["VALIDATOR ID", "NAME", "TYPE"], indent="  ")
