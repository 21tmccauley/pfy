"""Pure-engine tests, using data shaped like the prototypes' sample bundle."""

import json

from pfy.core.validator import bundle
from pfy.core.validator.detect import failing_records
from pfy.core.validator.diff import diff
from pfy.core.validator.models import Classification, Severity
from pfy.core.validator.replay import replay
from pfy.core.validator.triage import triage

VALIDATOR = {
    "id": "b2c3",
    "name": "VAL-7",
    "statement": "Scan must report zero critical severity findings",
    "type": "AUTOMATED",
    "regex": r'"critical_count":\s*(\d+)',
    "validationRules": [
        {
            "regexOperation": {"type": "MATCH_GROUP", "groupNumber": 1},
            "criteria": "LESS_THAN_OR_EQUAL_TO",
            "value": {"type": "CUSTOM_TEXT", "customText": "0"},
        }
    ],
}
# More changed fields than what_changed surfaces (3), so the ranking is exercised.
FAILING = {"summary": {"total_findings": 89, "critical_count": 3, "high_count": 12, "medium_count": 41}}  # noqa: E501
PASSING = {"summary": {"total_findings": 52, "critical_count": 0, "high_count": 7, "medium_count": 29}}  # noqa: E501


# --- replay --------------------------------------------------------------

def test_replay_reproduces_the_fail():
    rep = replay(VALIDATOR, json.dumps(FAILING))
    assert rep.available and rep.matches_found == 1
    rr = rep.rule_results[0]
    assert rr.extracted_value == "3"
    assert rr.passed is False


def test_replay_passes_on_compliant_content():
    rep = replay(VALIDATOR, json.dumps(PASSING))
    assert rep.rule_results[0].passed is True  # 0 <= 0


def test_replay_no_regex_is_unavailable():
    rep = replay({"name": "ATT", "validationRules": []}, "anything")
    assert rep.available is False and rep.note


def test_replay_uncompilable_regex_sets_error():
    rep = replay({"regex": "([", "validationRules": []}, "x")
    assert rep.error


# --- diff ----------------------------------------------------------------

def test_diff_reports_changed_leaves_with_delta():
    d = diff(FAILING, PASSING)
    assert d.available
    by_path = {c.path: c for c in d.changes}
    crit = by_path["summary.critical_count"]
    assert (crit.previous, crit.current, crit.delta) == (0, 3, 3)


def test_diff_unavailable_without_both_sides():
    assert diff(None, {}).available is False


# --- detect --------------------------------------------------------------

def _artifact(created, result):
    return {"createdAt": created, "validators": [{"id": "V", "name": "VAL", "result": result}]}


def test_detect_finds_streak_boundaries():
    artifacts = [
        _artifact("2026-01-01T00:00:00Z", "PASS"),
        _artifact("2026-02-01T00:00:00Z", "FAIL"),
        _artifact("2026-03-01T00:00:00Z", "FAIL"),
    ]
    (r,) = failing_records({"id": "E", "referenceId": "EVD-1"}, artifacts)
    assert r.validator_id == "V"
    assert r.last_passing["createdAt"] == "2026-01-01T00:00:00Z"
    assert r.first_failing["createdAt"] == "2026-02-01T00:00:00Z"
    assert r.current["createdAt"] == "2026-03-01T00:00:00Z"


def test_detect_no_baseline_when_never_passed():
    (r,) = failing_records({"id": "E"}, [_artifact("2026-02-01T00:00:00Z", "FAIL")])
    assert r.last_passing is None
    assert r.first_failing["createdAt"] == "2026-02-01T00:00:00Z"


def test_detect_ignores_currently_passing():
    assert failing_records({"id": "E"}, [_artifact("2026-02-01T00:00:00Z", "PASS")]) == []


# --- triage --------------------------------------------------------------

def test_triage_compliance_gap_is_high_when_criticals_rise():
    b = bundle.assemble(
        validator=VALIDATOR,
        evidence={"name": "Scan", "referenceId": "EVD-042"},
        failing_raw=json.dumps(FAILING),
        failing_content=FAILING,
        passing_raw=json.dumps(PASSING),
        passing_content=PASSING,
    )
    t = triage(b)
    assert t.classification == Classification.COMPLIANCE_GAP
    assert t.severity == Severity.HIGH
    assert t.what_changed and "critical_count" in t.what_changed
    assert "3" in t.why_failing


def test_triage_brittle_when_regex_matches_nothing():
    val = {**VALIDATOR, "regex": r'"nonexistent_key":\s*(\d+)'}
    b = bundle.assemble(
        validator=val,
        evidence={"name": "Scan"},
        failing_raw=json.dumps(FAILING),
        failing_content=FAILING,
    )
    t = triage(b)
    assert t.classification == Classification.BRITTLE_VALIDATOR
    assert t.what_changed is None  # no passing baseline provided
