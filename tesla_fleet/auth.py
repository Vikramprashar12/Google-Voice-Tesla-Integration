from __future__ import annotations

import json
import os
import secrets
import ssl
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

import requests

from .config import Config

AUTHORIZE_PATH = "/oauth2/v3/authorize"
TOKEN_PATH = "/oauth2/v3/token"


class TeslaAuthError(RuntimeError):
    pass


class TeslaAuth:
    """Handles the Tesla Fleet API OAuth2 authorization-code flow and token storage."""

    def __init__(self, config: Config):
        self.config = config

    # ---------- token cache ----------

    def load_tokens(self) -> Optional[dict]:
        path = Path(self.config.token_file)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_tokens(self, tokens: dict) -> None:
        tokens = dict(tokens)
        tokens["obtained_at"] = time.time()
        path = Path(self.config.token_file)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # best-effort on platforms without POSIX perms (e.g. Windows)

    # ---------- authorization-code flow ----------

    def build_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.config.scopes,
            "state": state,
        }
        return f"{self.config.auth_base}{AUTHORIZE_PATH}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        resp = requests.post(
            f"{self.config.auth_base}{TOKEN_PATH}",
            data={
                "grant_type": "authorization_code",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code": code,
                "redirect_uri": self.config.redirect_uri,
            },
            timeout=30,
        )
        if not resp.ok:
            raise TeslaAuthError(f"Token exchange failed ({resp.status_code}): {resp.text}")
        tokens = resp.json()
        self.save_tokens(tokens)
        return tokens

    def refresh(self, refresh_token: str) -> dict:
        resp = requests.post(
            f"{self.config.auth_base}{TOKEN_PATH}",
            data={
                "grant_type": "refresh_token",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        if not resp.ok:
            raise TeslaAuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")
        tokens = resp.json()
        # Tesla's refresh response omits refresh_token sometimes; keep the old one.
        tokens.setdefault("refresh_token", refresh_token)
        self.save_tokens(tokens)
        return tokens

    def get_valid_access_token(self) -> str:
        tokens = self.load_tokens()
        if not tokens:
            raise TeslaAuthError("No cached tokens found. Run `login` first.")
        obtained_at = tokens.get("obtained_at", 0)
        expires_in = tokens.get("expires_in", 0)
        # Refresh a bit early to avoid races against expiry.
        if time.time() >= obtained_at + max(expires_in - 60, 0):
            tokens = self.refresh(tokens["refresh_token"])
        return tokens["access_token"]

    # ---------- interactive login helper ----------

    def login_interactive(self, open_browser: bool = True) -> dict:
        """Runs the full authorization-code flow using a local HTTPS callback listener.

        `redirect_uri` in config must point at this machine (e.g.
        https://localhost:8585/callback) and must be registered exactly on the
        Tesla developer app.
        """
        parsed = urllib.parse.urlparse(self.config.redirect_uri)
        if parsed.hostname not in ("localhost", "127.0.0.1"):
            raise TeslaAuthError(
                "login_interactive only supports a localhost redirect_uri. "
                "For a non-localhost redirect_uri, use build_authorize_url() "
                "and exchange_code() manually."
            )
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        callback_path = parsed.path or "/callback"

        state = secrets.token_urlsafe(24)
        result: dict = {}
        server_ready = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence default logging
                pass

            def do_GET(self):
                req = urllib.parse.urlparse(self.path)
                if req.path != callback_path:
                    self.send_response(404)
                    self.end_headers()
                    return
                qs = urllib.parse.parse_qs(req.query)
                result["code"] = qs.get("code", [None])[0]
                result["state"] = qs.get("state", [None])[0]
                result["error"] = qs.get("error", [None])[0]
                body = (
                    b"<html><body><h3>Tesla authorization complete.</h3>"
                    b"You can close this tab and return to the terminal.</body></html>"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        httpd = HTTPServer((parsed.hostname, port), Handler)

        if parsed.scheme == "https":
            certfile, keyfile = _self_signed_cert(parsed.hostname)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        server_ready.set()

        auth_url = self.build_authorize_url(state)
        print("Open this URL in a browser to authorize the app:\n")
        print(auth_url)
        print()
        if open_browser:
            import webbrowser

            webbrowser.open(auth_url)

        print(f"Waiting for callback on {self.config.redirect_uri} ...")
        try:
            while "code" not in result and "error" not in result:
                time.sleep(0.25)
        finally:
            httpd.shutdown()

        if result.get("error"):
            raise TeslaAuthError(f"Authorization denied/error: {result['error']}")
        if result.get("state") != state:
            raise TeslaAuthError("State mismatch on OAuth callback; possible CSRF, aborting.")
        if not result.get("code"):
            raise TeslaAuthError("No authorization code received.")

        return self.exchange_code(result["code"])


def _self_signed_cert(hostname: str) -> tuple[str, str]:
    """Generates a throwaway self-signed cert for the local OAuth callback listener.

    Tesla's redirect_uri validation and the local browser only need *a* TLS
    listener to exist at the registered redirect_uri; the browser will show a
    one-time self-signed warning, which is expected for a localhost dev
    listener.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(x509.datetime.datetime.utcnow())
        .not_valid_after(x509.datetime.datetime.utcnow() + x509.datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(key, hashes.SHA256())
    )

    tmp_dir = tempfile.mkdtemp(prefix="tesla_oauth_cb_")
    certfile = os.path.join(tmp_dir, "cert.pem")
    keyfile = os.path.join(tmp_dir, "key.pem")
    with open(certfile, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(keyfile, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    return certfile, keyfile
