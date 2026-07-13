"""``pfy mcp`` — serve pfy's workflows to an AI agent over the Model Context Protocol.

The same core, a second face: the MCP tools call the identical service functions
the CLI commands do (see ``pfy.app.mcp_server``). Runs over stdio, so an agent host
launches it as ``pfy mcp`` and speaks MCP on the process's stdin/stdout.

Requires the optional ``mcp`` extra; this command imports it lazily so the base
CLI stays dependency-light and the install hint is friendly if it's missing.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import typer

from pfy.app.cli.context import Context

if TYPE_CHECKING:
    from pfy.app.settings import Settings


def _startup_notice(settings: Settings) -> str:
    """The banner shown when the server starts.

    Emitted on **stderr**, never stdout: stdio is the MCP transport, so any bytes
    on stdout that aren't protocol frames corrupt the stream. The MCP spec lets a
    server log to stderr, so a client that launches ``pfy mcp`` sees this in its
    logs and a human running it sees it in the terminal. Without it the command
    looks like a hung shell — it's actually blocked waiting for a client to speak.
    """
    url = settings.paramify_url
    env = "stage" if "stage." in url else "prod" if "app.paramify" in url else "custom"
    key = "set" if settings.paramify_api_key else "NOT set — export PARAMIFY_API_KEY"
    return "\n".join(
        [
            "pfy MCP server — ready, speaking MCP over stdio.",
            f"  paramify : {url} ({env})",
            f"  api key  : {key}",
            "  Not an interactive prompt — waiting for an MCP client on stdin/stdout.",
            "  Press Ctrl-C to stop.",
        ]
    )


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
    # stderr only — stdout is the protocol channel from here on.
    typer.echo(_startup_notice(c.settings), err=True)
    serve(c)
