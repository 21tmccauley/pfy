"""``pfy vuln`` — CVSS scoring and Paramify deviation sync. Porcelain.

These commands orchestrate multiple steps (NVD fetch + pure scoring + idempotent
deviation planning) into one job. The logic lives in ``app.services`` + ``core``;
these functions just parse args, call the service, and render.
"""

from __future__ import annotations

import typer

from pfy.app import output
from pfy.app.cli.context import Context
from pfy.app.services import IssueResult, ScoreResult, score_cves
from pfy.app.services import adjust_program as run_adjust
from pfy.core.vuln.selection import cvss_score_to_level

app = typer.Typer(no_args_is_help=True)


@app.command("score")
def score(
    ctx: typer.Context,
    cve_ids: list[str] = typer.Argument(..., help="One or more CVE IDs"),
    json_out: output.JSONOption = False,
) -> None:
    """Max NVD CVSS base score across the given CVEs."""
    c: Context = ctx.obj
    result = score_cves(c.nvd, cve_ids)

    def human(r: ScoreResult) -> None:
        nvd = "—" if r.nvd_score is None else f"{r.nvd_score} ({cvss_score_to_level(r.nvd_score)})"
        typer.echo(f"NVD score:   {nvd}")
        typer.echo(f"Winning CVE: {r.winning_cve or '—'}")
        typer.echo(f"Vector:      {r.winning_vector or '—'}")
        for w in r.warnings:
            typer.echo(f"warn: {w}", err=True)

    output.emit(result, as_json=json_out, human=human)
    raise typer.Exit(0 if result.nvd_score is not None else 1)


@app.command("adjust-program")
def adjust_program(
    ctx: typer.Context,
    program_id: str | None = typer.Option(None, "--program-id", help="Defaults to PROGRAM_ID"),
    post_deviations: bool = typer.Option(
        False, "--post-deviations", help="Write deviations back to Paramify"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Compute the plan (would-create/update); write nothing"
    ),
    json_out: output.JSONOption = False,
) -> None:
    """Score a program's CVE-bearing issues from NVD and sync their deviations."""
    c: Context = ctx.obj
    write = post_deviations and not dry_run
    results = run_adjust(c.paramify, c.nvd, c.settings, program_id=program_id, write=write)

    def human(rows: list[IssueResult]) -> None:
        for r in rows:
            label = r.poam_id or r.issue_id
            s = r.score
            if s.nvd_score is None:
                nvd = "—"
            else:
                nvd = f"{s.nvd_score}({cvss_score_to_level(s.nvd_score)})"
            dev = f"\tdeviation={r.deviation_action}" if r.deviation_action else ""
            typer.echo(f"{label}\t{r.title or ''}\tNVD={nvd}\tCVE={s.winning_cve or '—'}{dev}")
        if dry_run:
            typer.echo("(dry-run: no writes performed)", err=True)

    output.emit(results, as_json=json_out, human=human)
    raise typer.Exit(0 if results else 1)
