"""Heuristic triage — turn a Bundle into a baseline TriageResult.

Pure and deterministic: this is the analysis both prototypes did in code (the
orchestration prototype's fallback + the skill's six-point reasoning), distilled
to what can be decided without a model. An AI-narrative delivery can enrich or
override the prose; this stands on its own.
"""

from __future__ import annotations

from pfy.core.validator.models import (
    Bundle,
    Classification,
    DiffChange,
    RegexReplay,
    RuleResult,
    Severity,
    TriageResult,
)

_REMEDIATION = {
    Classification.COMPLIANCE_GAP: (
        "Remediate the underlying finding the rule flags, then re-upload the evidence artifact."
    ),
    Classification.BRITTLE_VALIDATOR: (
        "The evidence may be compliant — the validator's regex/rules don't match the artifact's "
        "actual shape. Fix the validator definition (or the artifact format) and re-run."
    ),
    Classification.DATA_ISSUE: (
        "The artifact couldn't be evaluated (wrong file, not JSON, or schema drift). "
        "Upload the expected artifact and re-run."
    ),
}


def triage(bundle: Bundle) -> TriageResult:
    rep = bundle.regex_replay
    failing = [r for r in rep.rule_results if r.passed is False]
    classification = _classify(rep, failing)
    return TriageResult(
        validator_id=bundle.validator_id,
        validator_name=bundle.validator_name,
        evidence_name=bundle.evidence_name,
        what_it_checks=bundle.statement or "Regex/rule checks over the uploaded evidence artifact.",
        why_failing=_why(rep, failing),
        what_changed=_what_changed(bundle),
        classification=classification,
        remediation=_REMEDIATION[classification],
        severity=_severity(bundle, classification),
    )


def _classify(rep: RegexReplay, failing: list[RuleResult]) -> Classification:
    if not rep.available:
        return Classification.DATA_ISSUE  # no regex to replay (attestation-type)
    if rep.error:
        return Classification.BRITTLE_VALIDATOR  # regex didn't compile
    if rep.matches_found == 0:
        return Classification.BRITTLE_VALIDATOR  # regex didn't match the artifact shape
    if failing:
        return Classification.COMPLIANCE_GAP  # a rule genuinely tripped
    return Classification.DATA_ISSUE


def _why(rep: RegexReplay, failing: list[RuleResult]) -> str:
    if failing:
        return failing[0].explanation
    if rep.error:
        return rep.error
    if not rep.available:
        return rep.note or "Validator has no regex to replay."
    if rep.matches_found == 0:
        return "The validator regex matched nothing in the failing artifact."
    unevaluated = [
        r for r in rep.rule_results if r.passed is None and r.extracted_value is not None
    ]
    if unevaluated:
        return unevaluated[0].explanation
    return "Marked FAIL upstream, but no rule failed locally — reason from the raw values."


def _what_changed(bundle: Bundle) -> str | None:
    if not bundle.has_passing_baseline:
        return None
    if not bundle.diff.available:
        return bundle.diff.reason
    changes = bundle.diff.changes
    if not changes:
        return "No leaf-level changes from the last passing artifact."
    # Security-salient paths first (a critical/severity count is the point of most
    # scan validators), then the biggest numeric moves.
    def _rank(c: DiffChange) -> tuple[int, bool, float]:
        salient = 0 if any(t in c.path.lower() for t in ("critical", "severity")) else 1
        return (salient, c.delta is None, -abs(c.delta or 0))

    return "; ".join(_fmt_change(c) for c in sorted(changes, key=_rank)[:3])


def _fmt_change(c: DiffChange) -> str:
    text = f"{c.path}: {c.previous} → {c.current}"
    if c.delta is not None:
        n = int(c.delta) if float(c.delta).is_integer() else c.delta
        text += f" ({'+' if c.delta >= 0 else ''}{n})"
    return text


def _severity(bundle: Bundle, classification: Classification) -> Severity:
    if classification == Classification.COMPLIANCE_GAP:
        if bundle.diff.available:
            for c in bundle.diff.changes:
                if c.delta is not None and c.delta > 0 and "critical" in c.path.lower():
                    return Severity.HIGH  # criticals went up — security-relevant
        return Severity.MEDIUM
    if classification == Classification.BRITTLE_VALIDATOR:
        return Severity.MEDIUM  # may be masking a real gap — needs a human
    return Severity.LOW
