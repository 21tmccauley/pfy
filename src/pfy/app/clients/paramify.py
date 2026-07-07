"""Paramify access — a thin facade over the installed ``paramify-sdk``.

The SDK owns transport (bearer auth, base URL, pooling, retries, typed errors).
This facade returns plain ``dict``s (via ``model_dump``) rather than SDK models,
converting at the transport boundary so the SDK's types never leak up into the
pure ``core`` logic — the same reason the ``core``/``app`` split exists.

``request`` is the raw escape hatch (backs ``pfy api``): any endpoint, still
authed/pooled/retried, no response model. Errors are the SDK's typed exceptions
(``ParamifyAuthError`` on 401/403, etc.) — import them from ``paramify_sdk`` to
catch them.
"""

from __future__ import annotations

from typing import Any

from paramify_sdk import ParamifyClient as _SdkClient

from pfy.app.settings import Settings


class ParamifyClient:
    """pfy-shaped facade over ``paramify_sdk.ParamifyClient``."""

    def __init__(self, settings: Settings) -> None:
        # The SDK builds its own pooled httpx client. pfy's settings default
        # paramify_url to *stage*, overriding the SDK's prod default.
        self._sdk = _SdkClient(
            api_key=settings.paramify_api_key,
            base_url=settings.paramify_url,
        )

    def close(self) -> None:
        self._sdk.close()

    def list_programs(self) -> list[dict[str, Any]]:
        return [p.model_dump(exclude_none=True) for p in self._sdk.list_programs()]

    def get_issues(
        self,
        *,
        project_id: str | None = None,
        issue_ids: list[str] | None = None,
        poam_ids: list[str] | None = None,
        cve_ids: list[str] | None = None,
        deviation_type: str | None = None,
        kev: bool | None = None,
        internet_reachable: bool | None = None,
        likely_exploitable: bool | None = None,
    ) -> list[dict[str, Any]]:
        issues = self._sdk.get_issues(
            project_id=project_id,
            issue_ids=issue_ids,
            poam_ids=poam_ids,
            cve_ids=cve_ids,
            deviation_type=deviation_type,
            kev=kev,
            internet_reachable=internet_reachable,
            likely_exploitable=likely_exploitable,
        )
        return [i.model_dump(exclude_none=True) for i in issues]

    def list_evidence(
        self, *, reference_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        return [
            e.model_dump(exclude_none=True)
            for e in self._sdk.list_evidence(reference_ids=reference_ids)
        ]

    def list_artifacts(self, evidence_id: str) -> list[dict[str, Any]]:
        return [
            a.model_dump(exclude_none=True)
            for a in self._sdk.list_artifacts(evidence_id)
        ]

    def list_validators(self) -> list[dict[str, Any]]:
        return [v.model_dump(exclude_none=True) for v in self._sdk.list_validators()]

    def get_validator(self, validator_id: str) -> dict[str, Any]:
        return self._sdk.get_validator(validator_id).model_dump(exclude_none=True)

    def create_deviation(self, issue_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._sdk.create_deviation(issue_id, body).model_dump(exclude_none=True)

    def update_deviation(
        self, issue_id: str, deviation_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        return self._sdk.update_deviation(issue_id, deviation_id, body).model_dump(
            exclude_none=True
        )

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Raw call to any endpoint (the SDK escape hatch). Returns parsed JSON."""
        return self._sdk.request(method, path, **kwargs)
