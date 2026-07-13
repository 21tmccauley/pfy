"""MCP delivery wiring — the tools are registered with usable schemas, and the
`pfy mcp` command announces startup on stderr. Skipped when the optional ``mcp``
extra isn't installed (``pip install 'pfy[mcp]'``)."""

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("mcp")

from pfy.app import mcp_server  # noqa: E402  (import after importorskip)
from pfy.app.cli.commands import mcp as mcp_cmd  # noqa: E402
from pfy.app.settings import Settings  # noqa: E402


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


def test_startup_notice_flags_env_and_api_key():
    prod = mcp_cmd._startup_notice(
        Settings(paramify_url="https://app.paramify.com/api/v0", paramify_api_key="x")
    )
    assert "(prod)" in prod and "stdio" in prod

    missing = mcp_cmd._startup_notice(
        Settings(paramify_url="https://stage.paramify.com/api/v0", paramify_api_key=None)
    )
    assert "(stage)" in missing and "NOT set" in missing


def test_mcp_command_announces_on_stderr_not_stdout(monkeypatch, capsys):
    # serve() blocks on stdio forever; replace it so the command returns. Then the
    # banner must land on stderr — stdout is the MCP transport and must stay clean.
    monkeypatch.setattr("pfy.app.mcp_server.serve", lambda ctx: None)
    fake_ctx = SimpleNamespace(settings=Settings(paramify_api_key="x"))
    mcp_cmd.mcp(SimpleNamespace(obj=fake_ctx))

    captured = capsys.readouterr()
    assert "MCP server" in captured.err
    assert captured.out == ""
