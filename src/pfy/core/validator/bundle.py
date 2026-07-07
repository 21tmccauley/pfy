"""Assemble a self-contained analysis Bundle from already-fetched parts.

Pure: the app layer fetches the validator definition and downloads the artifacts;
this ties them together and runs the deterministic replay + diff. ``failing_raw``
is the raw artifact text (replay needs it); ``*_content`` is the parsed JSON (diff
needs it), or ``None`` when the artifact wasn't JSON.
"""

from __future__ import annotations

from typing import Any

from pfy.core.validator.diff import diff
from pfy.core.validator.models import Bundle
from pfy.core.validator.replay import replay


def assemble(
    *,
    validator: dict[str, Any],
    evidence: dict[str, Any],
    failing_raw: str,
    failing_content: Any,
    passing_raw: str = "",
    passing_content: Any = None,
    failing_name: str | None = None,
    passing_name: str | None = None,
) -> Bundle:
    return Bundle(
        validator_id=validator.get("id") or validator.get("name") or "?",
        validator_name=validator.get("name"),
        evidence_name=evidence.get("name"),
        evidence_ref=evidence.get("referenceId"),
        statement=validator.get("statement"),
        regex_replay=replay(validator, failing_raw),
        diff=diff(failing_content, passing_content),
        has_passing_baseline=passing_content is not None or bool(passing_raw),
        failing_artifact_name=failing_name,
        last_passing_artifact_name=passing_name,
    )
