"""Diff a failing artifact against the last-passing one.

Pure: flatten both JSON structures to leaf paths and report the leaves that
changed (with a numeric delta where both sides are numbers). Lists collapse to a
count so a huge array doesn't drown the signal.
"""

from __future__ import annotations

from typing import Any

from pfy.core.validator.models import Diff, DiffChange


def _as_number(s: Any) -> float | None:
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return None


def _flatten(obj: Any, prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        out[prefix] = f"[{len(obj)} items]"
    else:
        out[prefix] = obj
    return out


def diff(failing_content: Any, passing_content: Any) -> Diff:
    """Changed leaves between failing and last-passing artifact content."""
    if failing_content is None or passing_content is None:
        return Diff(available=False, reason="Need both artifacts' JSON content to diff.")
    cur = _flatten(failing_content)
    prev = _flatten(passing_content)
    changes: list[DiffChange] = []
    for key in sorted(set(cur) | set(prev)):
        c, p = cur.get(key), prev.get(key)
        if c == p:
            continue
        cn, pn = _as_number(c), _as_number(p)
        delta = cn - pn if cn is not None and pn is not None else None
        changes.append(DiffChange(path=key, previous=p, current=c, delta=delta))
    return Diff(available=True, changes=changes)
