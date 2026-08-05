from __future__ import annotations

from typing import Any, Optional

import requests

from .auth import TeslaAuth
from .config import Config


class TeslaApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, payload: Any = None):
        super().__init__(f"Tesla API error {status_code}: {message}")
        self.status_code = status_code
        self.payload = payload


class TeslaFleetClient:
    """Thin client over the Tesla Fleet API.

    Read-only / account endpoints (vehicle list, vehicle_data, wake_up,
    region discovery) are called directly against `config.fleet_api_base`.

    Vehicle *commands* (lock, honk, climate, charging, etc.) require Tesla's
    end-to-end command signing on 2021+ vehicles, so those are routed through
    a locally running `tesla-http-proxy` at `config.proxy_base` instead of
    Tesla's servers directly. See README.md for how to set that up.
    """

    def __init__(self, config: Config, auth: TeslaAuth):
        self.config = config
        self.auth = auth
        self.session = requests.Session()

    # ---------- low-level request helpers ----------

    def _headers(self) -> dict:
        token = self.auth.get_valid_access_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _request(self, method: str, base: str, path: str, *, verify: bool = True, **kwargs) -> Any:
        url = f"{base}{path}"
        resp = self.session.request(method, url, headers=self._headers(), timeout=30, verify=verify, **kwargs)
        if resp.status_code == 401:
            # Token may have just expired mid-flight; refresh once and retry.
            tokens = self.auth.load_tokens()
            if tokens:
                self.auth.refresh(tokens["refresh_token"])
                resp = self.session.request(
                    method, url, headers=self._headers(), timeout=30, verify=verify, **kwargs
                )
        if not resp.ok:
            try:
                payload = resp.json()
                message = payload.get("error", resp.text)
            except ValueError:
                payload, message = None, resp.text
            raise TeslaApiError(resp.status_code, message, payload)
        if resp.content:
            return resp.json()
        return None

    def _get(self, path: str) -> Any:
        return self._request("GET", self.config.fleet_api_base, path)

    def _post_direct(self, path: str, json: Optional[dict] = None) -> Any:
        return self._request("POST", self.config.fleet_api_base, path, json=json or {})

    def _post_proxy(self, path: str, json: Optional[dict] = None) -> Any:
        return self._request(
            "POST", self.config.proxy_base, path, json=json or {}, verify=self.config.proxy_verify_ssl
        )

    # ---------- account / region ----------

    def discover_region(self) -> dict:
        """Looks up which regional Fleet API base URL this account should use."""
        data = self._get("/api/1/users/region")
        return data.get("response", data)

    # ---------- vehicles: read-only ----------

    def list_vehicles(self) -> list[dict]:
        data = self._get("/api/1/vehicles")
        return data.get("response", [])

    def vehicle(self, vehicle_tag: str) -> dict:
        data = self._get(f"/api/1/vehicles/{vehicle_tag}")
        return data.get("response", data)

    def vehicle_data(self, vehicle_tag: str, endpoints: Optional[list[str]] = None) -> dict:
        path = f"/api/1/vehicles/{vehicle_tag}/vehicle_data"
        if endpoints:
            path += "?endpoints=" + "%3B".join(endpoints)
        data = self._get(path)
        return data.get("response", data)

    def wake_up(self, vehicle_tag: str) -> dict:
        data = self._post_direct(f"/api/1/vehicles/{vehicle_tag}/wake_up")
        return data.get("response", data)

    def fleet_status(self, vehicle_tags: list[str]) -> dict:
        return self._post_direct("/api/1/vehicles/fleet_status", json={"vins": vehicle_tags})

    # ---------- vehicles: commands (signed, via proxy) ----------

    def command(self, vehicle_tag: str, command_name: str, params: Optional[dict] = None) -> dict:
        data = self._post_proxy(f"/api/1/vehicles/{vehicle_tag}/command/{command_name}", json=params or {})
        return data.get("response", data)
