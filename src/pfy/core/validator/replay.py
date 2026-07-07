"""Deterministic regex/rule replay — reproduce a validator FAIL locally.

Pure: (validator definition, raw artifact text) -> RegexReplay. Best-effort —
rules it can't auto-evaluate come back with ``passed=None`` and the raw extracted
value kept, so a downstream reasoner still has the operand to judge.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pfy.core.validator.models import RegexReplay, RuleResult

_NUMERIC_CRITERIA: dict[str, Callable[[float, float], bool]] = {
    "LESS_THAN_OR_EQUAL_TO": lambda a, b: a <= b,
    "GREATER_THAN_OR_EQUAL_TO": lambda a, b: a >= b,
    "LESS_THAN": lambda a, b: a < b,
    "GREATER_THAN": lambda a, b: a > b,
    "EQUAL_TO": lambda a, b: a == b,
    "EQUALS": lambda a, b: a == b,
    "NOT_EQUAL_TO": lambda a, b: a != b,
}

_STRING_CRITERIA: dict[str, Callable[[str, str], bool]] = {
    "CONTAINS": lambda a, b: b in a,
    "NOT_CONTAINS": lambda a, b: b not in a,
    "DOES_NOT_CONTAIN": lambda a, b: b not in a,
    "STARTS_WITH": lambda a, b: a.startswith(b),
    "ENDS_WITH": lambda a, b: a.endswith(b),
    "MATCHES": lambda a, b: re.search(b, a) is not None,
}

# Human-readable verb per criteria, for explanations.
_CRITERIA_VERB = {
    "LESS_THAN_OR_EQUAL_TO": "≤", "GREATER_THAN_OR_EQUAL_TO": "≥",
    "LESS_THAN": "<", "GREATER_THAN": ">", "EQUAL_TO": "equals", "EQUALS": "equals",
    "NOT_EQUAL_TO": "≠", "NOT_EQUALS": "≠",
    "CONTAINS": "contains", "NOT_CONTAINS": "does not contain",
    "DOES_NOT_CONTAIN": "does not contain", "STARTS_WITH": "starts with",
    "ENDS_WITH": "ends with", "MATCHES": "matches",
}


def _as_number(s: Any) -> float | None:
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def _eval_criteria(
    criteria: str | None, extracted: str | None, comparison: str | None
) -> bool | None:
    """Evaluate (extracted vs comparison) under ``criteria``. None = couldn't evaluate."""
    if extracted is None or comparison is None or not criteria:
        return None
    crit = criteria.upper()
    num = _NUMERIC_CRITERIA.get(crit)
    a, b = _as_number(extracted), _as_number(comparison)
    if num and a is not None and b is not None:
        return num(a, b)
    if crit in ("EQUALS", "EQUAL_TO"):
        return extracted == comparison
    if crit in ("NOT_EQUALS", "NOT_EQUAL_TO"):
        return extracted != comparison
    sfn = _STRING_CRITERIA.get(crit)
    if sfn is not None:
        try:
            return sfn(extracted, comparison)
        except re.error:
            return None
    return None


def replay(validator: dict[str, Any], raw_text: str) -> RegexReplay:
    """Compile the validator's regex, run its rules over ``raw_text``."""
    regex = validator.get("regex")
    rules = validator.get("validationRules") or []
    if not regex:
        return RegexReplay(
            available=False, regex=None,
            note="Validator has no regex (likely attestation-type); see attestationRules.",
        )
    try:
        compiled = re.compile(regex)
    except re.error as e:
        return RegexReplay(
            available=True, regex=regex, error=f"Validator regex did not compile: {e}"
        )

    matches = list(compiled.finditer(raw_text or ""))
    return RegexReplay(
        available=True,
        regex=regex,
        matches_found=len(matches),
        matches=[m.group(0) for m in matches[:10]],
        rule_results=[_replay_rule(idx, rule, matches) for idx, rule in enumerate(rules)],
    )


def _replay_rule(idx: int, rule: dict[str, Any], matches: list[re.Match[str]]) -> RuleResult:
    op = rule.get("regexOperation") or {}
    optype = op.get("type")
    criteria = rule.get("criteria")
    comparison = (rule.get("value") or {}).get("customText")
    disposition = (rule.get("disposition") or "PASS").upper()
    verb = _CRITERIA_VERB.get((criteria or "").upper(), criteria)

    # One operand per regex match, so "all X" rules check every match.
    extracted: list[str] = []
    if optype == "MATCH_GROUP":
        grp = op.get("groupNumber", 1)
        for m in matches:
            try:
                g = m.group(grp)
            except (IndexError, re.error):
                g = None
            if g is not None:
                extracted.append(g)
    elif optype == "MATCH_COUNT":
        extracted = [str(len(matches))]
    elif matches:
        extracted = [m.group(0) for m in matches]

    result = RuleResult(
        rule_index=idx,
        operation=optype,
        criteria=criteria,
        comparison_value=comparison,
        extracted_value=extracted[0] if extracted else None,
        extracted_values=extracted[:20],
    )

    if not extracted:
        result.explanation = "Regex produced no match to evaluate this rule against."
        return result

    evaluations = [(ev, _eval_criteria(criteria, ev, comparison)) for ev in extracted]
    if any(met is None for _, met in evaluations):
        sample = [ev for ev, _ in evaluations][:5]
        result.explanation = (
            f"Criteria {criteria!r} vs {comparison!r} not auto-evaluated for "
            f"value(s) {sample!r}. Reason from the raw value(s)."
        )
        return result

    failing = [
        ev for ev, met in evaluations if (met if disposition == "PASS" else not met) is False
    ]
    n = len(evaluations)
    result.passed = not failing
    if result.passed:
        result.explanation = (
            f'All {n} matched value(s) satisfy "{verb} {comparison}".'
            if n > 1 else f'Extracted value {verb} "{comparison}": {evaluations[0][0]!r}.'
        )
    else:
        result.explanation = (
            f'{len(failing)} of {n} matched value(s) fail "{verb} {comparison}". '
            f'First offending value: {failing[0]!r}.'
        )
    return result
