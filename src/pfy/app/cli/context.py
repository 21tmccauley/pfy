"""Per-invocation context: resolved settings + clients sharing one HTTP session.

Built once in the Typer root callback and stashed on ``ctx.obj``, so every command
receives the same constructed clients (the dependency-injection seam). This is the
only place that wires concrete clients to concrete settings.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from pfy.app.clients.http import make_client
from pfy.app.clients.nvd import NvdClient
from pfy.app.clients.paramify import ParamifyClient
from pfy.app.settings import Settings


@dataclass
class Context:
    settings: Settings
    http: httpx.Client
    nvd: NvdClient
    paramify: ParamifyClient

    def close(self) -> None:
        self.http.close()  # NVD's shared session
        self.paramify.close()  # the SDK's own pooled client


def build_context() -> Context:
    settings = Settings()
    http = make_client()
    return Context(
        settings=settings,
        http=http,
        nvd=NvdClient(http, settings),
        paramify=ParamifyClient(settings),  # SDK builds its own http pool
    )
