"""Unified output — the one place text-vs-JSON lives, so no command re-implements it.

A command builds its result (dataclass / pydantic model / dict / list) and hands
it to ``emit``. The JSON branch is generic (dataclasses and pydantic models
included); human output is a per-command callback, or ``emit_rows`` for the common
list-of-dicts table. ``JSONOption`` declares the ``--json`` flag once for reuse.

Design goal: human output is tab-separated so it stays awk/cut-friendly, and
``--json`` gives stable machine output. That single contract is what makes the
plumbing tier composable in a pipeline.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Annotated, Any

import typer

#: Reusable ``--json`` flag. Put ``json_out: output.JSONOption = False`` in a
#: command signature instead of re-declaring the option each time.
JSONOption = Annotated[bool, typer.Option("--json", help="Emit JSON instead of text.")]


def _jsonable(obj: Any) -> Any:
    """Coerce dataclasses / pydantic models / enums into JSON-serializable data."""
    if isinstance(obj, list):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump"):  # pydantic model
        return obj.model_dump(exclude_none=True)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _jsonable(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


def emit(data: Any, *, as_json: bool, human: Callable[[Any], None]) -> None:
    """Print ``data`` as indented JSON (``--json``) or via the ``human`` callback."""
    if as_json:
        typer.echo(json.dumps(_jsonable(data), indent=2, default=str))
    else:
        human(data)


def table(rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    """Tab-separated rows for a list of dicts — pipe/awk-friendly human output."""
    for row in rows:
        typer.echo("\t".join(_cell(row.get(c)) for c in columns))


def emit_rows(
    rows: Sequence[dict[str, Any]], columns: Sequence[str], *, as_json: bool
) -> None:
    """Shortcut for list-of-dicts commands: JSON, or a tab-separated table."""
    emit(list(rows), as_json=as_json, human=lambda rs: table(rs, columns))


def grid(
    rows: Sequence[dict[str, Any]],
    columns: Sequence[str],
    headers: Sequence[str] | None = None,
    *,
    indent: str = "",
) -> None:
    """Aligned table with a header row — report-style human output.

    Unlike ``table`` (tab-separated, for piping), ``grid`` pads each column to a
    common width and prints a header + underline, so it reads as a table in a
    terminal. Scripts should still consume ``--json``. ``headers`` defaults to the
    upper-cased column keys.
    """
    labels = list(headers) if headers is not None else [c.upper() for c in columns]
    body = [[_cell(row.get(c)) for c in columns] for row in rows]
    widths = [len(label) for label in labels]
    for cells in body:
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))

    def _line(cells: Sequence[str]) -> str:
        padded = "  ".join(cells[i].ljust(widths[i]) for i in range(len(columns)))
        return (indent + padded).rstrip()

    typer.echo(_line(labels))
    typer.echo(_line(["-" * w for w in widths]))
    for cells in body:
        typer.echo(_line(cells))


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)
