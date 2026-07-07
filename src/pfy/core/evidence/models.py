"""Typed I/O contract for the evidence-coverage capability.

Pure dataclasses so ``core`` stays dependency-free and these serialize straight
through ``app.output``. A CLI, a schedule, or an AI narrative can all consume one
shape — the same discipline as ``core.validator.models``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CoverageStatus(StrEnum):
    """How an evidence set relates to validators, given only what the API shows."""

    COVERED = "covered"  # ≥1 validator observed on an artifact
    NO_VALIDATOR = "no_validator"  # has artifacts, but none carry a validator
    NO_ARTIFACTS = "no_artifacts"  # no artifacts yet — nothing to observe a validator on


@dataclass
class EvidenceCoverage:
    """One evidence set bucketed by whether a validator was observed on it."""

    evidence_id: str
    reference_id: str | None
    name: str | None
    artifact_count: int
    status: CoverageStatus
    validator_ids: list[str] = field(default_factory=list)
    validator_names: list[str] = field(default_factory=list)


@dataclass
class OrphanValidator:
    """A catalog validator not observed on any evidence set's artifacts."""

    validator_id: str
    name: str | None
    type: str | None


@dataclass
class CoverageReport:
    """The full two-way gap report: evidence buckets + (optional) orphan validators.

    ``catalog_checked`` is False when the global validator catalog wasn't fetched
    (evidence-only mode), in which case ``orphan_validators`` is meaningless and
    stays empty.
    """

    covered: list[EvidenceCoverage] = field(default_factory=list)
    no_validator: list[EvidenceCoverage] = field(default_factory=list)
    no_artifacts: list[EvidenceCoverage] = field(default_factory=list)
    orphan_validators: list[OrphanValidator] = field(default_factory=list)
    catalog_checked: bool = False
