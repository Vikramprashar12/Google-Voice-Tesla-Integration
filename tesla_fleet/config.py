from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    client_id: str = field(default_factory=lambda: os.getenv("TESLA_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("TESLA_CLIENT_SECRET", ""))
    redirect_uri: str = field(
        default_factory=lambda: os.getenv("TESLA_REDIRECT_URI", "https://localhost:8585/callback")
    )
    scopes: str = field(
        default_factory=lambda: os.getenv(
            "TESLA_SCOPES",
            "openid offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds vehicle_location",
        )
    )
    fleet_api_base: str = field(
        default_factory=lambda: os.getenv(
            "TESLA_FLEET_API_BASE", "https://fleet-api.prd.na.vehicle-command.tesla.com"
        )
    )
    token_file: str = field(default_factory=lambda: os.getenv("TESLA_TOKEN_FILE", ".tesla_tokens.json"))
    proxy_base: str = field(default_factory=lambda: os.getenv("TESLA_PROXY_BASE", "https://localhost:4443"))
    proxy_verify_ssl: bool = field(default_factory=lambda: _bool_env("TESLA_PROXY_VERIFY_SSL", False))

    auth_base: str = "https://auth.tesla.com"

    def validate(self) -> None:
        missing = [
            name
            for name, val in (
                ("TESLA_CLIENT_ID", self.client_id),
                ("TESLA_CLIENT_SECRET", self.client_secret),
                ("TESLA_REDIRECT_URI", self.redirect_uri),
            )
            if not val
        ]
        if missing:
            raise ValueError(
                f"Missing required config: {', '.join(missing)}. "
                "Set them in a .env file (see .env.example) or as environment variables."
            )
