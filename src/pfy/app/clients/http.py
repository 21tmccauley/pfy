"""Shared HTTP client factory (NVD only).

One pooled ``httpx.Client`` per invocation, so connections are reused and the
timeout/retry policy lives in one place. Paramify doesn't use this — the SDK owns
its own pooled client and retry policy.
"""

from __future__ import annotations

import httpx


def make_client(timeout: float = 60.0) -> httpx.Client:
    transport = httpx.HTTPTransport(retries=2)
    return httpx.Client(timeout=timeout, transport=transport)
