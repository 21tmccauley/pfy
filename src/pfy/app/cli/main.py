"""Typer application root: build the Context, mount command groups, dispatch.

Two tiers live side by side:
  * plumbing groups (programs, issues, deviations) — thin, one-resource, JSON-first
  * porcelain groups (vuln)                        — opinionated multi-step workflows
plus ``api`` — the raw escape hatch to any endpoint.

Adding a group = write a module in ``commands/`` exposing a ``typer.Typer`` named
``app``, then ``add_typer`` it below.
"""

import typer

from pfy.app.cli.commands import (
    api,
    deviations,
    evidence,
    issues,
    programs,
    validator,
    vuln,
)
from pfy.app.cli.context import build_context

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="pfy — the Paramify FDE CLI (porcelain workflows + plumbing primitives).",
)


@app.callback()
def _root(ctx: typer.Context) -> None:
    context = build_context()
    ctx.obj = context
    ctx.call_on_close(context.close)  # close the shared HTTP sessions on exit


# Plumbing — decomposed, scriptable primitives.
app.add_typer(programs.app, name="programs", help="Programs/projects (plumbing).")
app.add_typer(issues.app, name="issues", help="Issues + inline deviations (plumbing).")
app.add_typer(deviations.app, name="deviations", help="Create/update deviations (plumbing).")
app.add_typer(evidence.app, name="evidence", help="Evidence sets + validator coverage.")

# Porcelain — opinionated workflows.
app.add_typer(vuln.app, name="vuln", help="CVSS scoring + deviation sync (porcelain).")
app.add_typer(validator.app, name="validator", help="Triage failing validators.")

# Escape hatch — raw request to any endpoint.
app.command("api", help="Raw request to any endpoint (escape hatch).")(api.api)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
