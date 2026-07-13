"""CLI wiring smoke tests — no network. The Paramify client is faked by
monkeypatching build_context, so we exercise command registration + the output
contract without hitting the API.
"""

import json
from types import SimpleNamespace

import pytest
from paramify_sdk import ParamifyAuthError, ParamifyConfigError
from typer.testing import CliRunner

import pfy.app.cli.main as main
from pfy.app.settings import Settings

runner = CliRunner()


class FakeParamify:
    def list_programs(self):
        return [{"id": "P1", "name": "Prog One"}, {"id": "P2", "name": "Prog Two"}]

    def get_issues(self, **kwargs):
        return [
            {"id": "ISS-1", "poamId": "POAM-1", "title": "Log4j", "cveIds": ["CVE-2021-44228"]},
            {"id": "ISS-2", "poamId": None, "title": "No CVEs", "cveIds": []},
        ]

    def request(self, method, path, **kwargs):
        return {
            "method": method,
            "path": path,
            "params": kwargs.get("params"),
            "body": kwargs.get("json"),
        }

    def close(self):
        pass


def _fake_context():
    return SimpleNamespace(settings=Settings(), paramify=FakeParamify(), close=lambda: None)


def test_help_lists_all_groups():
    result = runner.invoke(main.app, ["--help"])
    assert result.exit_code == 0
    for name in ("programs", "issues", "deviations", "evidence", "vuln", "mcp", "api"):
        assert name in result.output


def test_pfy_json_env_forces_json_without_flag(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    monkeypatch.setenv("PFY_JSON", "1")
    result = runner.invoke(main.app, ["programs", "list"])  # note: no --json
    assert result.exit_code == 0, result.output
    assert [p["id"] for p in json.loads(result.output)] == ["P1", "P2"]


def test_mcp_command_hints_when_extra_missing(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    import importlib.util

    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: None if name == "mcp" else real(name, *a, **k),
    )
    result = runner.invoke(main.app, ["mcp"])
    assert result.exit_code == 1
    assert "pip install 'pfy[mcp]'" in result.output


def test_triage_empty_run_exits_zero(monkeypatch):
    """Nothing failing is a successful run, not an error (exit 0, not 1)."""
    fake = SimpleNamespace(
        settings=Settings(),
        http=None,
        paramify=SimpleNamespace(list_evidence=lambda reference_ids=None: [], close=lambda: None),
        close=lambda: None,
    )
    monkeypatch.setattr(main, "build_context", lambda: fake)
    result = runner.invoke(main.app, ["validator", "triage"])
    assert result.exit_code == 0, result.output


def test_programs_list_json(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    result = runner.invoke(main.app, ["programs", "list", "--json"])
    assert result.exit_code == 0, result.output
    assert [p["id"] for p in json.loads(result.output)] == ["P1", "P2"]


def test_programs_list_text_is_tab_separated(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    result = runner.invoke(main.app, ["programs", "list"])
    assert result.exit_code == 0, result.output
    assert "P1\tProg One" in result.output


def test_program_get_missing_exits_2(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    result = runner.invoke(main.app, ["programs", "get", "NOPE"])
    assert result.exit_code == 2


def test_issues_list_has_cves_filters(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    args = ["issues", "list", "--program-id", "P1", "--has-cves", "--json"]
    result = runner.invoke(main.app, args)
    assert result.exit_code == 0, result.output
    assert [i["id"] for i in json.loads(result.output)] == ["ISS-1"]


def test_issues_list_without_scope_is_clean_usage_error(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    result = runner.invoke(main.app, ["issues", "list"])
    assert result.exit_code == 2
    # CLI vocabulary in the message, and no leaked traceback.
    assert "--program-id" in result.output
    assert "Traceback" not in result.output


def _run_expecting_exit(monkeypatch, argv, raiser):
    """Drive the real entrypoint (main.run) with a paramify client that raises,
    capturing the SystemExit code. run() — not CliRunner — owns error handling."""
    fake = SimpleNamespace(settings=Settings(), paramify=raiser, close=lambda: None)
    monkeypatch.setattr(main, "build_context", lambda: fake)
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as exc:
        main.run()
    return exc.value.code


def test_missing_api_key_prints_clean_error_not_traceback(monkeypatch, capsys):
    def boom():
        raise ParamifyConfigError("api_key is not set — set PARAMIFY_API_KEY")

    code = _run_expecting_exit(
        monkeypatch, ["pfy", "programs", "list"], SimpleNamespace(list_programs=boom)
    )
    err = capsys.readouterr().err
    assert code == 1
    assert err.startswith("Error: api_key is not set")
    assert "docs/setup.md" in err  # the config hint
    assert "Traceback" not in err


def test_auth_error_hints_at_stage_vs_prod(monkeypatch, capsys):
    def boom():
        raise ParamifyAuthError(401, "GET", "programs", {"error": "unauthorized"})

    code = _run_expecting_exit(
        monkeypatch, ["pfy", "programs", "list"], SimpleNamespace(list_programs=boom)
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "stage" in err and "prod" in err
    assert "Traceback" not in err


def test_api_escape_hatch_forwards_method_path_and_params(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    result = runner.invoke(main.app, ["api", "get", "evidence", "-p", "projectId=P1"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "GET"
    assert payload["path"] == "evidence"
    assert payload["params"] == {"projectId": "P1"}
