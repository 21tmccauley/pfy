"""Orchestration for validator triage — the I/O around the pure engine.

The Paramify API has no "list failing validators" endpoint, so we walk it via the
SDK's typed methods:

    list_evidence()               -> evidence sets
    list_artifacts(evidence_id)   -> artifacts (each carries validators[])
    get_validator(validator_id)   -> the validator definition (regex/rules)
    GET <artifact.pathname>       -> the raw artifact (presigned URL, plain http)

Presigned artifact URLs must NOT get the Paramify bearer token, so they're fetched
with the plain (unauthed) http client, not the SDK. All reasoning is pure ``core``.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import httpx

from pfy.app.clients.paramify import ParamifyClient
from pfy.core.validator import bundle as bundle_mod
from pfy.core.validator.detect import FailingRecord, failing_records
from pfy.core.validator.models import Bundle, TriageResult
from pfy.core.validator.triage import triage

#: Most-severe first. Shared by every delivery (CLI, MCP) so triage output is
#: ordered identically no matter who calls it.
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def sort_by_severity(results: list[TriageResult]) -> list[TriageResult]:
    """Order triage results high -> medium -> low (unknown severities last)."""
    return sorted(results, key=lambda t: SEVERITY_ORDER.get(t.severity, 9))


def triage_payload(result: TriageResult, *, compact: bool = False) -> dict[str, Any]:
    """Serialize a ``TriageResult`` to a plain JSON-ready dict.

    ``compact`` drops the long ``what_it_checks`` narrative — cheaper for an agent
    that only needs the verdict, why, what-changed, and remediation.
    """
    data = dataclasses.asdict(result)
    data["classification"] = result.classification.value
    data["severity"] = result.severity.value
    if compact:
        data.pop("what_it_checks", None)
    return data


def find_failing(
    paramify: ParamifyClient, *, evidence_refs: list[str] | None = None
) -> list[FailingRecord]:
    """Walk evidence -> artifacts and return every currently-failing validator."""
    records: list[FailingRecord] = []
    for evidence in paramify.list_evidence(reference_ids=evidence_refs):
        evidence_id = evidence.get("id")
        if not evidence_id:
            continue
        artifacts = paramify.list_artifacts(evidence_id)
        records.extend(failing_records(evidence, artifacts))
    return records


def _download(http: httpx.Client, pathname: str | None) -> tuple[str, Any]:
    """Fetch a presigned artifact URL (no auth). Returns (raw_text, parsed_json_or_None)."""
    if not pathname:
        return "", None
    resp = http.get(pathname)
    resp.raise_for_status()
    raw = resp.text
    try:
        return raw, json.loads(raw)
    except ValueError:
        return raw, None


def build_bundle(paramify: ParamifyClient, http: httpx.Client, record: FailingRecord) -> Bundle:
    validator = paramify.get_validator(record.validator_id)
    first, last = record.first_failing or {}, record.last_passing or {}
    fail_raw, fail_content = _download(http, first.get("pathname"))
    pass_raw, pass_content = "", None
    if record.last_passing:
        pass_raw, pass_content = _download(http, last.get("pathname"))
    return bundle_mod.assemble(
        validator=validator,
        evidence=record.evidence,
        failing_raw=fail_raw,
        failing_content=fail_content,
        passing_raw=pass_raw,
        passing_content=pass_content,
        failing_name=first.get("originalFileName"),
        passing_name=last.get("originalFileName") if record.last_passing else None,
    )


def triage_live(
    paramify: ParamifyClient,
    http: httpx.Client,
    *,
    evidence_refs: list[str] | None = None,
    limit: int | None = None,
) -> list[TriageResult]:
    """Full workflow: find failing validators, build bundles, run heuristic triage."""
    records = find_failing(paramify, evidence_refs=evidence_refs)
    if limit:
        records = records[:limit]
    return [triage(build_bundle(paramify, http, rec)) for rec in records]


def triage_files(
    validator_path: Path,
    failing_path: Path,
    passing_path: Path | None,
    evidence_name: str | None,
) -> TriageResult:
    """Triage a hand-collected example offline — same engine, no API."""
    validator = json.loads(validator_path.read_text())
    fail_raw, fail_content = _read(failing_path)
    pass_raw, pass_content = _read(passing_path) if passing_path else ("", None)
    bundle = bundle_mod.assemble(
        validator=validator,
        evidence={"name": evidence_name or "(manually provided evidence)"},
        failing_raw=fail_raw,
        failing_content=fail_content,
        passing_raw=pass_raw,
        passing_content=pass_content,
        failing_name=failing_path.name,
        passing_name=passing_path.name if passing_path else None,
    )
    return triage(bundle)


def _read(path: Path) -> tuple[str, Any]:
    raw = path.read_text()
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError:
        return raw, None
