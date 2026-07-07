"""Centralized configuration (pydantic-settings).

Resolution order, highest precedence first:
    explicit init args  >  environment variables  >  .env file  >  field defaults

Paramify defaults to STAGE on purpose — FDE tools are built/tested there first.
A stage token against the prod default 401s, which reads like a bad token but is
really a wrong-environment mismatch.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paramify
    paramify_url: str = "https://stage.paramify.com/api/v0"
    paramify_api_key: str | None = None
    program_id: str | None = None

    # NVD (vuln commands)
    nvd_url: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    nvd_api_key: str | None = None

    # Deviation defaults
    deviation_type: str = "RISK_ADJUSTMENT"
    deviation_method: str = "EXAMINE"
    deviation_status: str = "PENDING"
