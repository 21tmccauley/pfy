"""Coverage logic — bucket evidence sets and find orphan validators.

Pure functions over already-fetched dicts. Validators live per artifact at
``artifacts[].validators[]`` (id/name/result); a validator counts as *associated*
with an evidence set if it appears on any of that set's artifacts — presence is
the signal, not the PASS/FAIL verdict. This is the only evidence↔validator link
the API exposes, since the configured association (``POST .../associate``) has no
read endpoint.
"""

from __future__ import annotations

from typing import Any

from pfy.core.evidence.models import (
    CoverageReport,
    CoverageStatus,
    EvidenceCoverage,
    OrphanValidator,
)


def validators_on_artifacts(artifacts: list[dict[str, Any]]) -> dict[str, str | None]:
    """Deduped ``{validator_id: name}`` observed across an evidence set's artifacts."""
    found: dict[str, str | None] = {}
    for artifact in artifacts:
        for v in artifact.get("validators") or []:
            vid = v.get("id")
            if vid and vid not in found:
                found[vid] = v.get("name")
    return found


def classify_evidence(
    evidence: dict[str, Any], artifacts: list[dict[str, Any]]
) -> EvidenceCoverage:
    """Bucket one evidence set by whether a validator was observed on its artifacts.

    ``artifacts`` is the ground truth we walked — empty when the set has none (the
    app layer skips the fetch for zero-artifact sets), which yields NO_ARTIFACTS.
    """
    validators = validators_on_artifacts(artifacts)
    if validators:
        status = CoverageStatus.COVERED
    elif artifacts:
        status = CoverageStatus.NO_VALIDATOR
    else:
        status = CoverageStatus.NO_ARTIFACTS

    # Prefer the evidence's own count (authoritative even when we skipped the fetch).
    count = evidence.get("artifactCount")
    if not isinstance(count, int):
        count = len(artifacts)

    return EvidenceCoverage(
        evidence_id=evidence.get("id", ""),
        reference_id=evidence.get("referenceId"),
        name=evidence.get("name"),
        artifact_count=count,
        status=status,
        validator_ids=list(validators),
        validator_names=[name for name in validators.values() if name],
    )


def build_report(
    coverages: list[EvidenceCoverage],
    catalog: list[dict[str, Any]] | None,
) -> CoverageReport:
    """Group evidence coverages; if a validator catalog is given, flag orphans.

    ``catalog`` is the global ``GET /validators`` list. An orphan is a catalog
    validator whose id was never observed on any evidence set's artifacts. Pass
    ``None`` to skip the reverse direction (evidence-only report).
    """
    report = CoverageReport(catalog_checked=catalog is not None)
    for cov in coverages:
        if cov.status is CoverageStatus.COVERED:
            report.covered.append(cov)
        elif cov.status is CoverageStatus.NO_VALIDATOR:
            report.no_validator.append(cov)
        else:
            report.no_artifacts.append(cov)

    if catalog is not None:
        observed: set[str] = set()
        for cov in coverages:
            observed.update(cov.validator_ids)
        for v in catalog:
            vid = v.get("id")
            if vid and vid not in observed:
                report.orphan_validators.append(
                    OrphanValidator(
                        validator_id=vid, name=v.get("name"), type=v.get("type")
                    )
                )
    return report
