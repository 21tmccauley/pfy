"""Typer application root: build the Context, mount command groups, dispatch.

Two tiers live side by side:
  * plumbing groups (programs, issues, deviations) — thin, one-resource, JSON-first
  * porcelain groups (vuln)                        — opinionated multi-step workflows
plus ``api`` — the raw escape hatch to any endpoint.

Adding a group = write a module in ``commands/`` exposing a ``typer.Typer`` named
``app``, then add a row to the ``_GROUPS`` table below.
"""

import typer
from paramify_sdk import ParamifyAuthError, ParamifyConfigError, ParamifyError
from typer.core import TyperGroup

from pfy.app.cli.commands import (
    api,
    deviations,
    evidence,
    issues,
    mcp,
    programs,
    validator,
    vuln,
)
from pfy.app.cli.context import build_context


class _RootGroup(TyperGroup):
    """Order --help so panels read: command groups (in definition order), then the
    leaf commands, with the ``api`` escape hatch dead last.

    click's default ``list_commands`` sorts alphabetically; worse, Typer registers
    directly-added leaf commands (``mcp``, ``api``) *ahead* of ``add_typer`` groups,
    so left alone they'd float their panels above Workflows (rich orders panels by
    first appearance). The stable sort below keys on (is-leaf, is-api): groups sort
    first in registration order, then leaf commands, then ``api``.
    """

    def list_commands(self, ctx: typer.Context) -> list[str]:  # type: ignore[override]
        # The [override] ignore is because Typer's vendored click Context differs
        # from the public typer.Context; it avoids depending on that private import.
        def key(name: str) -> tuple[bool, bool]:
            # Groups carry a ``.commands`` dict; leaf commands (mcp, api) don't.
            is_leaf = not hasattr(self.commands[name], "commands")
            return (is_leaf, name == "api")

        return sorted(self.commands, key=key)


app = typer.Typer(
    cls=_RootGroup,
    no_args_is_help=True,
    add_completion=False,
    # Expected domain failures (ParamifyError: missing/wrong auth, missing scope,
    # 404s) are rendered as a clean one-line message in run() below. Turning off
    # Typer's rich traceback lets those propagate there instead of being dumped
    # as a scary source-frame traceback the first time a cold-start user slips.
    pretty_exceptions_enable=False,
    help="pfy — the Paramify FDE CLI (porcelain workflows + plumbing primitives).",
)


@app.callback()
def _root(ctx: typer.Context) -> None:
    context = build_context()
    ctx.obj = context
    ctx.call_on_close(context.close)  # close the shared HTTP sessions on exit


WORKFLOWS = "Workflows"  # opinionated, multi-step
PLUMBING = "Plumbing"  # thin, one-resource, JSON-first

# (module, name, help, --help panel). Panels appear in first-seen order, so
# workflows list above primitives; the ``api`` escape hatch is forced last by
# ``_RootGroup``. Add a row here to mount a new group.
_GROUPS = [
    (vuln, "vuln", "CVSS scoring + deviation sync.", WORKFLOWS),
    (validator, "validator", "Triage failing validators.", WORKFLOWS),
    (programs, "programs", "Programs/projects.", PLUMBING),
    (issues, "issues", "Issues + inline deviations.", PLUMBING),
    (deviations, "deviations", "Create/update deviations.", PLUMBING),
    (evidence, "evidence", "Evidence sets + validator coverage.", PLUMBING),
]
for module, name, help_text, panel in _GROUPS:
    app.add_typer(module.app, name=name, help=help_text, rich_help_panel=panel)

# Agent interface — serve the same workflows to an AI over MCP (stdio).
app.command(
    "mcp", help="Serve pfy workflows to an AI agent (MCP, stdio).", rich_help_panel="Agent"
)(mcp.mcp)

# Escape hatch — raw request to any endpoint (forced last in --help).
app.command("api", help="Raw request to any endpoint.", rich_help_panel="Escape hatch")(api.api)


def _fail(err: Exception, hint: str | None = None) -> None:
    """Print a domain error as ``Error: …`` (+ optional hint) to stderr, exit 1."""
    typer.echo(f"Error: {err}", err=True)
    if hint:
        typer.echo(f"Hint: {hint}", err=True)
    raise SystemExit(1)


def run() -> None:
    """Entrypoint. Turn the SDK's typed, expected errors into a clean message and
    a non-zero exit, so a user with no prior knowledge gets guidance instead of a
    traceback on their first misstep. Unexpected errors still surface in full.
    """
    try:
        app()
    except ParamifyAuthError as e:
        _fail(
            e,
            "Check PARAMIFY_API_KEY, and that PARAMIFY_URL matches the token's "
            "environment — a stage token against prod (or vice-versa) 401s.",
        )
    except ParamifyConfigError as e:
        _fail(e, "See required settings in .env.example / docs/setup.md.")
    except ParamifyError as e:
        _fail(e)


if __name__ == "__main__":
    run()
