"""Typed I/O contract for the failing-validator triage capability.

Pure dataclasses on purpose: ``core`` stays dependency-free and these serialize
straight through ``app.output``. The engine that produces them —
``replay`` / ``diff`` / ``detect`` / ``bundle`` / ``triage`` — is the deterministic
logic both prototypes duplicated, extracted here so a CLI, a schedule, or an AI
narrative can all consume one shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Classification(StrEnum):
    COMPLIANCE_GAP = "compliance_gap"  # evidence really is non-compliant
    BRITTLE_VALIDATOR = "brittle_validator"  # regex/rule doesn't match the real shape
    DATA_ISSUE = "data_issue"  # wrong file / not JSON / can't replay


@dataclass
class RuleResult:
    """One validation rule replayed locally against the failing artifact."""

    rule_index: int
    operation: str | None  # MATCH_GROUP | MATCH_COUNT | ...
    criteria: str | None  # LESS_THAN_OR_EQUAL_TO | CONTAINS | ...
    comparison_value: str | None
    extracted_value: str | None  # first matched operand
    extracted_values: list[str] = field(default_factory=list)
    passed: bool | None = None  # None = couldn't auto-evaluate; reason from the value
    explanation: str = ""


@dataclass
class RegexReplay:
    """The validator's regex + rules replayed over the failing artifact text."""

    available: bool  # False when the validator has no regex (attestation-type)
    regex: str | None
    matches_found: int = 0
    matches: list[str] = field(default_factory=list)
    rule_results: list[RuleResult] = field(default_factory=list)
    note: str | None = None
    error: str | None = None  # set if the regex didn't compile


@dataclass
class DiffChange:
    """A leaf that moved between the last-passing artifact and the failing one."""

    path: str
    previous: Any = None
    current: Any = None
    delta: float | None = None  # current - previous, when both are numeric


@dataclass
class Diff:
    available: bool
    changes: list[DiffChange] = field(default_factory=list)
    reason: str | None = None  # why unavailable (e.g. no passing baseline / not JSON)


@dataclass
class Bundle:
    """Everything needed to reason about one failing validator, self-contained."""

    validator_id: str
    validator_name: str | None
    evidence_name: str | None
    evidence_ref: str | None
    statement: str | None  # plain-English intent of the validator
    regex_replay: RegexReplay
    diff: Diff
    has_passing_baseline: bool
    failing_artifact_name: str | None = None
    last_passing_artifact_name: str | None = None


@dataclass
class TriageResult:
    """Baseline analysis for one failing validator — the promotable output shape.

    Deterministic and heuristic: an AI-narrative delivery can enrich or override
    the prose, but this stands on its own without any model.
    """

    validator_id: str
    validator_name: str | None
    evidence_name: str | None
    what_it_checks: str
    why_failing: str
    what_changed: str | None
    classification: Classification
    remediation: str
    severity: Severity
