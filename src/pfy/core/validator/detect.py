"""Failure detection — which validators are currently failing, and their streak.

Pure logic over already-fetched artifact dicts (the app layer does the fetching).
Pass/fail lives per artifact (``artifacts[].validators[].result``), so for each
validator failing on the newest artifact we walk its timeline to find the *first*
failure in the current streak and the *last passing* artifact before it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FAILING_RESULTS = {"FAIL", "ERROR"}
PASSING_RESULTS = {"PASS"}


@dataclass
class FailingRecord:
    """One (evidence, validator) failing on its newest artifact, with its streak."""

    evidence: dict[str, Any]
    validator_id: str
    validator_name: str
    current: dict[str, Any]  # newest artifact
    first_failing: dict[str, Any]  # first FAIL since the last PASS
    last_passing: dict[str, Any] | None


def _sort_key(artifact: dict[str, Any]) -> str:
    # createdAt is ISO-8601; lexical sort is chronological. Fall back to effectiveDate.
    return artifact.get("createdAt") or artifact.get("effectiveDate") or ""


def validator_result(artifact: dict[str, Any], validator_id: str) -> str | None:
    for v in artifact.get("validators") or []:
        if v.get("id") == validator_id:
            return (v.get("result") or "").upper() or None
    return None


def failing_records(
    evidence: dict[str, Any], artifacts: list[dict[str, Any]]
) -> list[FailingRecord]:
    """Records for every validator failing on this evidence set's newest artifact."""
    if not artifacts:
        return []
    ordered = sorted(artifacts, key=_sort_key)  # oldest -> newest
    newest = ordered[-1]

    records: list[FailingRecord] = []
    for v in newest.get("validators") or []:
        if (v.get("result") or "").upper() not in FAILING_RESULTS:
            continue
        validator_id = v.get("id")
        if not validator_id:
            continue

        timeline = [
            (a, validator_result(a, validator_id))
            for a in ordered
            if validator_result(a, validator_id) is not None
        ]
        last_passing: dict[str, Any] | None = None
        first_failing = timeline[-1][0]  # default: newest, if it never passed
        last_pass_idx = -1
        for i, (_, res) in enumerate(timeline):
            if res in PASSING_RESULTS:
                last_pass_idx = i
        if last_pass_idx >= 0:
            last_passing = timeline[last_pass_idx][0]
            for a, res in timeline[last_pass_idx + 1:]:
                if res in FAILING_RESULTS:
                    first_failing = a
                    break

        records.append(
            FailingRecord(
                evidence=evidence,
                validator_id=validator_id,
                validator_name=v.get("name") or validator_id,
                current=newest,
                first_failing=first_failing,
                last_passing=last_passing,
            )
        )
    return records
