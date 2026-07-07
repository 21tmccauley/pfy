"""Typer application root: build the Context, mount command groups, dispatch.

Two tiers live side by side:
  * plumbing groups (programs, issues, deviations) — thin, one-resource, JSON-first
  * porcelain groups (vuln)                        — opinionated multi-step workflows
plus ``api`` — the raw escape hatch to any endpoint.

Adding a group = write a module in ``commands/`` exposing a ``typer.Typer`` named
``app``, then add a row to the ``_GROUPS`` table below.
"""

import typer
from typer.core import TyperGroup

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


class _RootGroup(TyperGroup):
    """Order --help by definition order, with the ``api`` escape hatch last.

    click's default ``list_commands`` sorts alphabetically, which floats the
    first plumbing group above the Workflows panel (rich orders panels by first
    appearance). Iterating ``self.commands`` keeps registration order instead;
    the stable ``sorted`` then moves only ``api`` to the end.
    """

    def list_commands(self, ctx: typer.Context) -> list[str]:  # type: ignore[override]
        # The [override] ignore is because Typer's vendored click Context differs
        # from the public typer.Context; it avoids depending on that private import.
        return sorted(self.commands, key=lambda name: name == "api")


app = typer.Typer(
    cls=_RootGroup,
    no_args_is_help=True,
    add_completion=False,
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

# Escape hatch — raw request to any endpoint (forced last in --help).
app.command("api", help="Raw request to any endpoint.", rich_help_panel="Escape hatch")(api.api)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
