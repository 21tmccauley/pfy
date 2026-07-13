"""``pfy mcp`` — serve pfy's workflows to an AI agent over the Model Context Protocol.

The same core, a second face: the MCP tools call the identical service functions
the CLI commands do (see ``pfy.app.mcp_server``). Runs over stdio, so an agent host
launches it as ``pfy mcp`` and speaks MCP on the process's stdin/stdout.

Requires the optional ``mcp`` extra; this command imports it lazily so the base
CLI stays dependency-light and the install hint is friendly if it's missing.
"""

from __future__ import annotations

import importlib.util

import typer

from pfy.app.cli.context import Context


def mcp(ctx: typer.Context) -> None:
    """Serve pfy workflows as MCP tools for an AI agent (stdio transport)."""
    # mcp_server imports FastMCP lazily, so check the package here (not via a
    # failed import of mcp_server) to give a clean install hint when it's absent.
    if importlib.util.find_spec("mcp") is None:
        typer.echo(
            "Error: MCP support isn't installed. Install it with:\n"
            "  pip install 'pfy[mcp]'",
            err=True,
        )
        raise typer.Exit(1)
    from pfy.app.mcp_server import serve

    c: Context = ctx.obj
    serve(c)
