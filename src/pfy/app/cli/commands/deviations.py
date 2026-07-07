"""``pfy deviations`` — create/update deviations. Plumbing.

The body is JSON (create needs ``description``, ``method``, ``type``,
``deviationMetadata``). Pass it with ``--body-file`` or pipe it in with
``--stdin`` so a write composes on the end of a pipeline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from pfy.app import output
from pfy.app.cli.context import Context

app = typer.Typer(no_args_is_help=True)


def _load_body(body_file: Path | None, stdin: bool) -> dict[str, Any]:
    if stdin and body_file:
        raise typer.BadParameter("use --stdin or --body-file, not both")
    if stdin:
        raw = sys.stdin.read()
    elif body_file:
        raw = body_file.read_text()
    else:
        raise typer.BadParameter("provide a body via --stdin or --body-file")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"body is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise typer.BadParameter("body must be a JSON object")
    return data


def _emit(dev: dict[str, Any], *, as_json: bool) -> None:
    output.emit(dev, as_json=as_json, human=lambda d: typer.echo(d.get("id", "(ok)")))


@app.command("create")
def create(
    ctx: typer.Context,
    issue_id: str = typer.Option(..., "--issue-id", help="Issue to attach the deviation to"),
    body_file: Path | None = typer.Option(None, "--body-file", help="JSON body file"),
    stdin: bool = typer.Option(False, "--stdin", help="Read the JSON body from stdin"),
    json_out: output.JSONOption = False,
) -> None:
    """Create a deviation on an issue."""
    c: Context = ctx.obj
    _emit(c.paramify.create_deviation(issue_id, _load_body(body_file, stdin)), as_json=json_out)


@app.command("update")
def update(
    ctx: typer.Context,
    issue_id: str = typer.Option(..., "--issue-id", help="Issue the deviation belongs to"),
    deviation_id: str = typer.Option(..., "--deviation-id", help="Deviation to update"),
    body_file: Path | None = typer.Option(None, "--body-file", help="JSON body file"),
    stdin: bool = typer.Option(False, "--stdin", help="Read the JSON body from stdin"),
    json_out: output.JSONOption = False,
) -> None:
    """Partially update an existing deviation."""
    c: Context = ctx.obj
    body = _load_body(body_file, stdin)
    _emit(c.paramify.update_deviation(issue_id, deviation_id, body), as_json=json_out)
