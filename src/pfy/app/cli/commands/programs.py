"""``pfy programs`` — list/get Paramify programs (projects). Plumbing."""

from __future__ import annotations

from typing import Any

import typer

from pfy.app import output
from pfy.app.cli.context import Context

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_(ctx: typer.Context, json_out: output.JSONOption = False) -> None:
    """List programs: id and name."""
    c: Context = ctx.obj
    output.emit_rows(c.paramify.list_programs(), ["id", "name"], as_json=json_out)


@app.command("get")
def get(
    ctx: typer.Context,
    program_id: str = typer.Argument(..., help="Program id"),
    json_out: output.JSONOption = False,
) -> None:
    """Get one program by id."""
    c: Context = ctx.obj
    match = next((p for p in c.paramify.list_programs() if p.get("id") == program_id), None)
    if match is None:
        typer.echo(f"program {program_id} not found", err=True)
        raise typer.Exit(2)

    def human(p: dict[str, Any]) -> None:
        typer.echo(f"{p['id']}\t{p.get('name', '')}")

    output.emit(match, as_json=json_out, human=human)
