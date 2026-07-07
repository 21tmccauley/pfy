"""CLI tests for `pfy evidence coverage` — a fake Paramify walks evidence ->
artifacts -> validators, no network.
"""

import json
from types import SimpleNamespace

from typer.testing import CliRunner

import pfy.app.cli.main as main
from pfy.app.settings import Settings

runner = CliRunner()

EVIDENCES = [
    {"id": "E1", "referenceId": "EVD-1", "name": "Covered", "artifactCount": 1},
    {"id": "E2", "referenceId": "EVD-2", "name": "Unvalidated", "artifactCount": 1},
    {"id": "E3", "referenceId": "EVD-3", "name": "Empty", "artifactCount": 0},
]
ARTIFACTS = {
    "E1": [{"validators": [{"id": "V1", "name": "One", "result": "PASS"}]}],
    "E2": [{"validators": []}],
}
VALIDATORS = [
    {"id": "V1", "name": "One", "type": "AUTOMATED"},
    {"id": "V9", "name": "Nine", "type": "ATTESTATION"},  # orphan
]


class FakeParamify:
    """Stands in for the SDK-backed facade: typed-method calls, not raw request()."""

    def __init__(self):
        self.calls = []

    def list_evidence(self, *, reference_ids=None):
        self.calls.append(("list_evidence", reference_ids))
        return EVIDENCES

    def list_artifacts(self, evidence_id):
        self.calls.append(("list_artifacts", evidence_id))
        return ARTIFACTS.get(evidence_id, [])

    def list_validators(self):
        self.calls.append(("list_validators", None))
        return VALIDATORS

    def close(self):
        pass


def _ctx(fake):
    return lambda: SimpleNamespace(settings=Settings(), paramify=fake, close=lambda: None)


def test_evidence_help_lists_coverage():
    result = runner.invoke(main.app, ["evidence", "--help"])
    assert result.exit_code == 0
    assert "coverage" in result.output


def test_coverage_json_buckets_and_orphans(monkeypatch):
    fake = FakeParamify()
    monkeypatch.setattr(main, "build_context", _ctx(fake))
    result = runner.invoke(main.app, ["evidence", "coverage", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)

    assert [c["evidence_id"] for c in report["covered"]] == ["E1"]
    assert [c["evidence_id"] for c in report["no_validator"]] == ["E2"]
    assert [c["evidence_id"] for c in report["no_artifacts"]] == ["E3"]
    assert [o["validator_id"] for o in report["orphan_validators"]] == ["V9"]
    # zero-artifact evidence is bucketed without an artifacts fetch
    assert ("list_artifacts", "E3") not in fake.calls


def test_coverage_no_orphans_skips_catalog(monkeypatch):
    fake = FakeParamify()
    monkeypatch.setattr(main, "build_context", _ctx(fake))
    result = runner.invoke(main.app, ["evidence", "coverage", "--no-orphans", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["catalog_checked"] is False
    assert report["orphan_validators"] == []
    assert ("list_validators", None) not in fake.calls


def test_coverage_human_output_is_grouped(monkeypatch):
    monkeypatch.setattr(main, "build_context", _ctx(FakeParamify()))
    result = runner.invoke(main.app, ["evidence", "coverage"])
    assert result.exit_code == 0, result.output
    out = result.output
    # summary + section tables with headers
    assert "SUMMARY" in out and "BUCKET" in out
    assert "REFERENCE" in out and "VALIDATOR ID" in out
    # the unvalidated evidence set and the orphan validator both appear
    assert "EVD-2" in out and "Unvalidated" in out
    assert "V9" in out and "Nine" in out
