"""Offline CLI tests for `pfy validator` — replay/diff/triage over local files,
no network. build_context is real (constructs the SDK client but never calls it).
"""

import json

from typer.testing import CliRunner

import pfy.app.cli.main as main

runner = CliRunner()

VALIDATOR = {
    "name": "VAL-7",
    "statement": "Scan must report zero critical findings",
    "regex": r'"critical_count":\s*(\d+)',
    "validationRules": [
        {
            "regexOperation": {"type": "MATCH_GROUP", "groupNumber": 1},
            "criteria": "LESS_THAN_OR_EQUAL_TO",
            "value": {"type": "CUSTOM_TEXT", "customText": "0"},
        }
    ],
}
FAILING = {"summary": {"critical_count": 3}}
PASSING = {"summary": {"critical_count": 0}}


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return str(p)


def test_validator_help_lists_commands():
    result = runner.invoke(main.app, ["validator", "--help"])
    assert result.exit_code == 0
    for cmd in ("list-failing", "replay", "diff", "triage"):
        assert cmd in result.output


def test_replay_offline_json(tmp_path):
    args = [
        "validator", "replay",
        "--validator", _write(tmp_path, "val.json", VALIDATOR),
        "--failing", _write(tmp_path, "fail.json", FAILING),
        "--json",
    ]
    result = runner.invoke(main.app, args)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["matches_found"] == 1
    assert data["rule_results"][0]["passed"] is False


def test_diff_offline_json(tmp_path):
    args = [
        "validator", "diff",
        "--failing", _write(tmp_path, "fail.json", FAILING),
        "--passing", _write(tmp_path, "pass.json", PASSING),
        "--json",
    ]
    result = runner.invoke(main.app, args)
    assert result.exit_code == 0, result.output
    changes = {c["path"]: c for c in json.loads(result.output)["changes"]}
    assert changes["summary.critical_count"]["current"] == 3


def test_triage_offline_json(tmp_path):
    args = [
        "validator", "triage",
        "--validator", _write(tmp_path, "val.json", VALIDATOR),
        "--failing", _write(tmp_path, "fail.json", FAILING),
        "--passing", _write(tmp_path, "pass.json", PASSING),
        "--json",
    ]
    result = runner.invoke(main.app, args)
    assert result.exit_code == 0, result.output
    results = json.loads(result.output)
    assert results[0]["classification"] == "compliance_gap"
    assert results[0]["severity"] == "high"
