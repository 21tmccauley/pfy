"""Offline CLI tests for `pfy validator` — replay/diff/triage over local files,
no network. build_context is real (constructs the SDK client but never calls it).
"""

import json

from typer.testing import CliRunner

import pfy.app.cli.main as main
from pfy.app import validator_service
from pfy.core.validator.models import Classification, Severity, TriageResult

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


def test_triage_compact_omits_narrative(tmp_path):
    args = [
        "validator", "triage",
        "--validator", _write(tmp_path, "val.json", VALIDATOR),
        "--failing", _write(tmp_path, "fail.json", FAILING),
        "--passing", _write(tmp_path, "pass.json", PASSING),
        "--compact", "--json",
    ]
    result = runner.invoke(main.app, args)
    assert result.exit_code == 0, result.output
    r = json.loads(result.output)[0]
    assert "what_it_checks" not in r  # the long narrative is dropped
    assert r["classification"] == "compliance_gap"  # everything else survives


def test_triage_payload_compact_flag():
    """The shared serializer used by both the CLI and the MCP tool."""
    r = TriageResult(
        validator_id="v", validator_name="V", evidence_name="E",
        what_it_checks="a long narrative", why_failing="w", what_changed=None,
        classification=Classification.COMPLIANCE_GAP, remediation="fix",
        severity=Severity.HIGH,
    )
    full = validator_service.triage_payload(r, compact=False)
    assert full["what_it_checks"] == "a long narrative"
    assert full["classification"] == "compliance_gap"  # StrEnum -> plain value
    assert full["severity"] == "high"
    assert "what_it_checks" not in validator_service.triage_payload(r, compact=True)
