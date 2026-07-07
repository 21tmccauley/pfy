"""``pfy issues`` — list/get issues (their deviations ride along inline). Plumbing."""

from __future__ import annotations

from typing import Any

import typer

from pfy.app import output
from pfy.app.cli.context import Context

app = typer.Typer(no_args_is_help=True)


def _human(rows: list[dict[str, Any]]) -> None:
    for i in rows:
        cves = ", ".join(i.get("cveIds") or [])
        typer.echo(f"{i.get('poamId') or i['id']}\t{i.get('title', '')}\t{cves}")


@app.command("list")
def list_(
    ctx: typer.Context,
    program_id: str | None = typer.Option(None, "--program-id", help="Defaults to PROGRAM_ID"),
    poam_id: list[str] | None = typer.Option(None, "--poam-id", help="POA&M id (repeatable)"),
    cve_id: list[str] | None = typer.Option(None, "--cve-id", help="CVE id (repeatable)"),
    kev: bool = typer.Option(False, "--kev", help="Only KEV vulnerabilities"),
    has_cves: bool = typer.Option(False, "--has-cves", help="Only issues carrying CVE ids"),
    json_out: output.JSONOption = False,
) -> None:
    """List issues. Needs a scope: program id (or PROGRAM_ID), poam id, or cve id."""
    c: Context = ctx.obj
    issues = c.paramify.get_issues(
        project_id=program_id or c.settings.program_id,
        poam_ids=poam_id or None,
        cve_ids=cve_id or None,
        kev=kev or None,
    )
    if has_cves:
        issues = [i for i in issues if i.get("cveIds")]
    output.emit(issues, as_json=json_out, human=_human)


@app.command("get")
def get(
    ctx: typer.Context,
    issue_id: str = typer.Argument(..., help="Issue id"),
    json_out: output.JSONOption = False,
) -> None:
    """Get one issue (with its inline deviations) by id."""
    c: Context = ctx.obj
    issues = c.paramify.get_issues(issue_ids=[issue_id])
    if not issues:
        typer.echo(f"issue {issue_id} not found", err=True)
        raise typer.Exit(2)
    output.emit(issues[0], as_json=json_out, human=lambda i: _human([i]))
