"""``pfy api`` — raw request to any endpoint (the SDK ``request()`` escape hatch).

The bottom rung: hit an endpoint that has no typed primitive yet, still authed,
pooled, and retried. Prints raw JSON so it composes.

    pfy api GET issues --param projectId=PRJ-1 --param kev=true
    pfy api POST issues/ISS-1/deviations --stdin < body.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

import typer

from pfy.app.cli.context import Context


def api(
    ctx: typer.Context,
    method: str = typer.Argument(..., help="HTTP method, e.g. GET, POST, PATCH"),
    path: str = typer.Argument(..., help="Path relative to the base URL, e.g. 'issues'"),
    param: list[str] | None = typer.Option(
        None, "--param", "-p", help="Query param key=value (repeatable)"
    ),
    stdin: bool = typer.Option(False, "--stdin", help="Read a JSON request body from stdin"),
) -> None:
    """Call any endpoint and print the raw JSON response."""
    c: Context = ctx.obj
    params: dict[str, str] = {}
    for item in param or []:
        if "=" not in item:
            raise typer.BadParameter(f"--param must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        params[key] = value

    body: Any = None
    if stdin:
        try:
            body = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"stdin is not valid JSON: {e}") from e

    result = c.paramify.request(method.upper(), path, params=params or None, json=body)
    typer.echo(json.dumps(result, indent=2, default=str))
