"""MCP delivery wiring — the tools are registered with usable schemas. Skipped
when the optional ``mcp`` extra isn't installed (``pip install 'pfy[mcp]'``)."""

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("mcp")

from pfy.app import mcp_server  # noqa: E402  (import after importorskip)


def _tools():
    # build_server only *registers* tools (it doesn't call them), so a stand-in
    # Context with null clients is enough to introspect the schemas.
    ctx = SimpleNamespace(paramify=None, http=None, nvd=None, settings=None)
    server = mcp_server.build_server(ctx)
    return {t.name: t for t in asyncio.run(server.list_tools())}


def test_build_server_exposes_the_full_tool_surface():
    tools = _tools()
    assert {
        "validator_list_failing",
        "validator_triage",
        "evidence_coverage",
        "vuln_score",
        "vuln_adjust_program",
        "programs_list",
        "issues_list",
        "issues_get",
    } <= set(tools)


def test_triage_exposes_the_levers_an_agent_needs():
    triage = _tools()["validator_triage"]
    assert set(triage.inputSchema["properties"]) == {"evidence_refs", "limit", "compact"}
    assert triage.description and "classification" in triage.description


def test_adjust_program_defaults_to_a_dry_run():
    # The one write-capable tool: `write` must exist and default False, and the
    # description must make the dry-run/mutation distinction explicit.
    adjust = _tools()["vuln_adjust_program"]
    props = adjust.inputSchema["properties"]
    assert set(props) == {"program_id", "write"}
    assert props["write"].get("default") is False
    assert adjust.description and "DRY RUN" in adjust.description


def test_issues_list_scoping_params():
    props = _tools()["issues_list"].inputSchema["properties"]
    assert set(props) == {"program_id", "poam_ids", "cve_ids", "kev", "has_cves"}
