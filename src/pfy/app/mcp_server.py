"""MCP delivery — pfy's porcelain workflows exposed as Model Context Protocol tools.

A second ``app/`` delivery beside the CLI, over the *same* shared service layer:
each tool calls the identical ``validator_service`` / ``evidence_service`` /
``services`` functions the CLI commands call and returns the identical shapes
(coerced with ``output.jsonable``, exactly as ``--json`` does). No workflow logic
lives here — only the tool surface and its schemas — so the CLI and an AI agent
can never drift.

Requires the optional ``mcp`` extra (bundled in the release binary; from a source
checkout, ``pip install -e '.[mcp]'``); ``pfy mcp`` imports this module lazily and
prints an install hint if it's missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pfy.app import evidence_service, output, services, validator_service

if TYPE_CHECKING:
    from pfy.app.cli.context import Context


# --- helpers: one per tool, taking the invocation Context, so the tool bodies
# --- below stay one line and the mapping to the shared service layer is obvious.


def _list_failing(ctx: Context, evidence_refs: list[str] | None) -> list[dict[str, Any]]:
    records = validator_service.find_failing(ctx.paramify, evidence_refs=evidence_refs or None)
    return [
        {
            "validator": r.validator_name,
            "validatorId": r.validator_id,
            "evidence": r.evidence.get("referenceId") or r.evidence.get("name"),
            "baseline": bool(r.last_passing),
        }
        for r in records
    ]


def _triage(
    ctx: Context, evidence_refs: list[str] | None, limit: int | None, compact: bool
) -> list[dict[str, Any]]:
    results = validator_service.triage_live(
        ctx.paramify, ctx.http, evidence_refs=evidence_refs or None, limit=limit
    )
    results = validator_service.sort_by_severity(results)
    return [validator_service.triage_payload(r, compact=compact) for r in results]


def _evidence_coverage(
    ctx: Context, evidence_refs: list[str] | None, orphans: bool
) -> dict[str, Any]:
    report = evidence_service.find_validator_coverage(
        ctx.paramify, evidence_refs=evidence_refs or None, check_catalog=orphans
    )
    # jsonable() is Any->Any; a dataclass always coerces to a dict, a list of them
    # to a list — the casts assert the shape we know without re-implementing it.
    return cast("dict[str, Any]", output.jsonable(report))


def _vuln_score(ctx: Context, cve_ids: list[str]) -> dict[str, Any]:
    return cast("dict[str, Any]", output.jsonable(services.score_cves(ctx.nvd, cve_ids)))


def _vuln_adjust_program(
    ctx: Context, program_id: str | None, write: bool
) -> list[dict[str, Any]]:
    results = services.adjust_program(
        ctx.paramify, ctx.nvd, ctx.settings, program_id=program_id, write=write
    )
    return cast("list[dict[str, Any]]", output.jsonable(results))


def _programs_list(ctx: Context) -> list[dict[str, Any]]:
    return ctx.paramify.list_programs()


def _issues_list(
    ctx: Context,
    program_id: str | None,
    poam_ids: list[str] | None,
    cve_ids: list[str] | None,
    kev: bool,
    has_cves: bool,
) -> list[dict[str, Any]]:
    program = program_id or ctx.settings.program_id
    if not (program or poam_ids or cve_ids):
        raise ValueError(
            "provide a scope: program_id (or set PROGRAM_ID), poam_ids, or cve_ids"
        )
    issues = ctx.paramify.get_issues(
        project_id=program,
        poam_ids=poam_ids or None,
        cve_ids=cve_ids or None,
        kev=kev or None,
    )
    return [i for i in issues if i.get("cveIds")] if has_cves else issues


def _issues_get(ctx: Context, issue_id: str) -> dict[str, Any]:
    issues = ctx.paramify.get_issues(issue_ids=[issue_id])
    if not issues:
        raise ValueError(f"issue {issue_id} not found")
    return issues[0]


def build_server(ctx: Context) -> Any:
    """Construct the FastMCP server, its tools bound to this invocation's ``ctx``."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("pfy")

    @server.tool()
    def validator_list_failing(
        evidence_refs: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Paramify validators currently failing on their newest artifact.

        evidence_refs: optionally limit to specific evidence referenceIds.
        Returns one row per failing validator (name, id, evidence, whether a
        last-passing baseline exists). This is the cheap survey before triage.
        """
        return _list_failing(ctx, evidence_refs)

    @server.tool()
    def validator_triage(
        evidence_refs: list[str] | None = None,
        limit: int | None = None,
        compact: bool = True,
    ) -> list[dict[str, Any]]:
        """Triage failing validators end to end: find -> bundle -> baseline analysis.

        Returns one result per failing validator, most-severe first, each with a
        classification (compliance_gap = evidence really regressed;
        brittle_validator = the regex/rule no longer matches the artifact's shape;
        data_issue = wrong file / not evaluable), a severity, why it's failing,
        what changed vs the last passing artifact, and a remediation.

        evidence_refs: limit to specific evidence referenceIds.
        limit: cap how many failing validators are analyzed.
        compact: omit the long what_it_checks narrative (default True to save tokens).
        """
        return _triage(ctx, evidence_refs, limit, compact)

    @server.tool()
    def evidence_coverage(
        evidence_refs: list[str] | None = None,
        orphans: bool = True,
    ) -> dict[str, Any]:
        """Report which evidence sets have no validator observed on any artifact.

        A validator counts as covering an evidence set only when it has run against
        one of that set's artifacts — the sole association the API exposes. The
        report buckets each set (covered / no-validator / no-artifacts-yet) and,
        when orphans=True, also lists catalog validators no evidence set uses.

        evidence_refs: limit to specific evidence referenceIds.
        orphans: also flag unused catalog validators (default True).
        """
        return _evidence_coverage(ctx, evidence_refs, orphans)

    @server.tool()
    def vuln_score(cve_ids: list[str]) -> dict[str, Any]:
        """Max NVD CVSS base score across the given CVEs.

        Returns the winning CVE, its score/vector, every selected metric, and any
        warnings (CVEs missing from NVD or lacking a usable metric).
        """
        return _vuln_score(ctx, cve_ids)

    @server.tool()
    def vuln_adjust_program(
        program_id: str | None = None,
        write: bool = False,
    ) -> list[dict[str, Any]]:
        """Score a program's CVE-bearing issues from NVD and plan their deviations.

        For each issue carrying cveIds: take the max NVD score and compute the
        idempotent deviation change. Returns one result per issue (score + the
        deviation action).

        write=False (default) is a DRY RUN — actions come back as would-create /
        would-update / unchanged and nothing is sent to Paramify. Set write=True to
        actually create/update the deviations (a mutation).

        program_id: defaults to the PROGRAM_ID setting.
        """
        return _vuln_adjust_program(ctx, program_id, write)

    @server.tool()
    def programs_list() -> list[dict[str, Any]]:
        """List Paramify programs (projects): id and name (plus any other fields)."""
        return _programs_list(ctx)

    @server.tool()
    def issues_list(
        program_id: str | None = None,
        poam_ids: list[str] | None = None,
        cve_ids: list[str] | None = None,
        kev: bool = False,
        has_cves: bool = False,
    ) -> list[dict[str, Any]]:
        """List issues (each with its inline deviations). Needs a scope.

        Provide at least one of: program_id (or set PROGRAM_ID), poam_ids, cve_ids.

        kev: only KEV vulnerabilities. has_cves: only issues carrying CVE ids.
        """
        return _issues_list(ctx, program_id, poam_ids, cve_ids, kev, has_cves)

    @server.tool()
    def issues_get(issue_id: str) -> dict[str, Any]:
        """Get one issue (with its inline deviations) by id."""
        return _issues_get(ctx, issue_id)

    return server


def serve(ctx: Context) -> None:
    """Run the pfy MCP server over stdio (blocks until the client disconnects)."""
    build_server(ctx).run(transport="stdio")
