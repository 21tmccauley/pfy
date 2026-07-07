"""Orchestration for evidence↔validator coverage — walk the API, run pure logic.

The Paramify API (v0.5.1) has no readable "which validators are configured on
this evidence set" link: that association is set write-only via
``POST /evidence/{id}/associate`` (``subjectType: VALIDATOR``). The only
*observable* association is that a validator has run against one of the evidence
set's artifacts. So coverage is derived by walking the SDK's typed methods:

    list_evidence()               -> evidence sets (each carries artifactCount)
    list_artifacts(evidence_id)   -> artifacts (each carries validators[])
    list_validators()             -> global catalog (for the orphan check)

Evidence sets with ``artifactCount == 0`` are bucketed as NO_ARTIFACTS without an
artifacts call — there is nothing to observe. All bucketing is pure ``core`` logic.
"""

from __future__ import annotations

from typing import Any

from pfy.app.clients.paramify import ParamifyClient
from pfy.core.evidence.coverage import build_report, classify_evidence
from pfy.core.evidence.models import CoverageReport, EvidenceCoverage


def find_validator_coverage(
    paramify: ParamifyClient,
    *,
    evidence_refs: list[str] | None = None,
    check_catalog: bool = True,
) -> CoverageReport:
    """Walk evidence -> artifacts, bucket each set, and (optionally) find orphans."""
    coverages: list[EvidenceCoverage] = []
    for evidence in paramify.list_evidence(reference_ids=evidence_refs):
        evidence_id = evidence.get("id")
        if not evidence_id:
            continue
        # Only skip the fetch on an explicit zero; a missing count is unknown, so walk.
        if evidence.get("artifactCount") == 0:
            artifacts: list[dict[str, Any]] = []
        else:
            artifacts = paramify.list_artifacts(evidence_id)
        coverages.append(classify_evidence(evidence, artifacts))

    catalog = paramify.list_validators() if check_catalog else None
    return build_report(coverages, catalog)
