"""CLI wiring smoke tests — no network. The Paramify client is faked by
monkeypatching build_context, so we exercise command registration + the output
contract without hitting the API.
"""

import json
from types import SimpleNamespace

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
    for name in ("programs", "issues", "deviations", "evidence", "vuln", "api"):
        assert name in result.output


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


def test_api_escape_hatch_forwards_method_path_and_params(monkeypatch):
    monkeypatch.setattr(main, "build_context", _fake_context)
    result = runner.invoke(main.app, ["api", "get", "evidence", "-p", "projectId=P1"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["method"] == "GET"
    assert payload["path"] == "evidence"
    assert payload["params"] == {"projectId": "P1"}
