"""Pure-engine tests for evidence↔validator coverage bucketing + orphan detection."""

from pfy.core.evidence.coverage import (
    build_report,
    classify_evidence,
    validators_on_artifacts,
)
from pfy.core.evidence.models import CoverageStatus


def _artifact(*validators):
    return {
        "validators": [{"id": vid, "name": name, "result": res} for vid, name, res in validators]
    }


# --- validators_on_artifacts ---------------------------------------------

def test_validators_on_artifacts_dedupes_by_id_across_artifacts():
    artifacts = [
        _artifact(("V1", "One", "PASS")),
        _artifact(("V1", "One", "FAIL"), ("V2", "Two", "PASS")),
    ]
    assert validators_on_artifacts(artifacts) == {"V1": "One", "V2": "Two"}


def test_validators_on_artifacts_ignores_entries_without_id():
    assert validators_on_artifacts([_artifact((None, "x", "PASS"))]) == {}


# --- classify_evidence ---------------------------------------------------

def test_covered_when_any_artifact_carries_a_validator():
    ev = {"id": "E1", "referenceId": "EVD-1", "name": "Scan", "artifactCount": 2}
    cov = classify_evidence(ev, [_artifact(), _artifact(("V", "VAL", "FAIL"))])
    assert cov.status is CoverageStatus.COVERED
    assert cov.validator_ids == ["V"] and cov.validator_names == ["VAL"]


def test_no_validator_when_artifacts_carry_none():
    cov = classify_evidence({"id": "E2", "artifactCount": 1}, [_artifact()])
    assert cov.status is CoverageStatus.NO_VALIDATOR


def test_no_artifacts_when_none_fetched():
    cov = classify_evidence({"id": "E3", "artifactCount": 0}, [])
    assert cov.status is CoverageStatus.NO_ARTIFACTS


def test_artifact_count_prefers_evidence_field_over_fetched_len():
    # count reported by the API even though we skipped the (zero) artifacts fetch
    cov = classify_evidence({"id": "E", "artifactCount": 7}, [])
    assert cov.artifact_count == 7


# --- build_report --------------------------------------------------------

def test_build_report_buckets_and_flags_orphans():
    covered = classify_evidence(
        {"id": "E1", "artifactCount": 1}, [_artifact(("V1", "One", "PASS"))]
    )
    unvalidated = classify_evidence({"id": "E2", "artifactCount": 1}, [_artifact()])
    empty = classify_evidence({"id": "E3", "artifactCount": 0}, [])
    catalog = [
        {"id": "V1", "name": "One", "type": "AUTOMATED"},  # observed -> not orphan
        {"id": "V9", "name": "Nine", "type": "ATTESTATION"},  # orphan
    ]

    report = build_report([covered, unvalidated, empty], catalog)

    assert [c.evidence_id for c in report.covered] == ["E1"]
    assert [c.evidence_id for c in report.no_validator] == ["E2"]
    assert [c.evidence_id for c in report.no_artifacts] == ["E3"]
    assert report.catalog_checked is True
    assert [o.validator_id for o in report.orphan_validators] == ["V9"]


def test_build_report_skips_orphans_when_catalog_is_none():
    report = build_report([], None)
    assert report.catalog_checked is False
    assert report.orphan_validators == []
