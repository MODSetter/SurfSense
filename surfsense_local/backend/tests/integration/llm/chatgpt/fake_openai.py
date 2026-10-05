"""Enough of OpenAI's sign-in and plan endpoints for the app to talk to.

Shaped after the open-source "Sign in with ChatGPT" docs: a dynamic client is
issued on first sign-in, refresh tokens rotate, and the plan lists its models
and answers on /v1/responses.
"""

import base64
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ISSUED_CLIENT = "app_issued_1"
ACCOUNT = "user-1"
EMAIL = "reader@example.com"
PLAN_SCOPE = (
    "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeOpenAI:
    def __init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._lock = threading.Lock()
        self._serial = 0
        self.refreshes = 0
        # Seconds a refresh takes, so two processes can be caught in one.
        self.refresh_delay = 0.0
        self.scope = PLAN_SCOPE
        self.authorized: list[dict[str, str]] = []
        self.revoked_refresh: set[str] = set()
        self.issued_refresh: list[str] = []
        # Each revocation request's form, as RFC 7009 sends it.
        self.revocations: list[dict[str, str]] = []
        self.revocation_down = False
        self.live_access: set[str] = set()
        self._codes: dict[str, dict[str, str]] = {}
        self.models = [
            {"slug": "gpt-5", "display_name": "GPT-5", "visibility": "list"},
            {"slug": "gpt-hidden", "display_name": "Hidden", "visibility": "hide"},
        ]
        self.answers: list[dict] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def tokens(self, client_id: str = ISSUED_CLIENT, nonce: str | None = None) -> dict:
        with self._lock:
            self._serial += 1
            serial = self._serial
        access = f"at-{serial}"
        self.live_access.add(access)
        self.issued_refresh.append(f"rt-{serial}")
        return {
            "access_token": access,
            "refresh_token": f"rt-{serial}",
            "id_token": self.id_token(client_id, nonce),
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": self.scope,
        }

    def id_token(self, client_id: str, nonce: str | None) -> str:
        header = {"alg": "RS256", "kid": "k1", "typ": "JWT"}
        claims = {
            "iss": self.url,
            "aud": client_id,
            "sub": ACCOUNT,
            "email": EMAIL,
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        if nonce is not None:
            claims["nonce"] = nonce
        signing = (
            f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
        )
        signature = self._key.sign(
            signing.encode(), padding.PKCS1v15(), hashes.SHA256()
        )
        return f"{signing}.{_b64(signature)}"

    def _jwks(self) -> dict:
        numbers = self._key.public_key().public_numbers()

        def b64int(value: int) -> str:
            return _b64(value.to_bytes((value.bit_length() + 7) // 8, "big"))

        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "k1",
                    "alg": "RS256",
                    "use": "sig",
                    "n": b64int(numbers.n),
                    "e": b64int(numbers.e),
                }
            ]
        }

    def _token_reply(self, form: dict[str, str]) -> tuple[int, dict]:
        if form.get("grant_type") == "authorization_code":
            grant = self._codes.pop(form.get("code", ""), None)
            verifier = form.get("code_verifier", "")
            challenge = _b64(hashlib.sha256(verifier.encode()).digest())
            if (
                grant is None
                or grant["code_challenge"] != challenge
                or grant["redirect_uri"] != form.get("redirect_uri")
                or form.get("client_id") != ISSUED_CLIENT
            ):
                return 400, {"error": "invalid_grant"}
            return 200, self.tokens(nonce=grant["nonce"])
        if form.get("grant_type") == "refresh_token":
            with self._lock:
                self.refreshes += 1
            time.sleep(self.refresh_delay)
            old = form.get("refresh_token", "")
            if old in self.revoked_refresh or not old.startswith("rt-"):
                return 400, {"error": "invalid_grant"}
            self.revoked_refresh.add(old)
            return 200, self.tokens()
        return 400, {"error": "unsupported_grant_type"}

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                parsed = urlsplit(self.path)
                if parsed.path == "/api/accounts/authorize":
                    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                    fake.authorized.append(params)
                    code = f"code-{len(fake.authorized)}"
                    fake._codes[code] = params
                    query = urlencode(
                        {
                            "code": code,
                            "state": params["state"],
                            "client_id": ISSUED_CLIENT,
                        }
                    )
                    self.send_response(302)
                    self.send_header("Location", f"{params['redirect_uri']}?{query}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                elif parsed.path == "/.well-known/jwks.json":
                    self._json(200, fake._jwks())
                elif parsed.path == "/v1/models":
                    if not self._authorized():
                        return
                    self._json(200, {"models": fake.models})
                else:
                    self._json(404, {"detail": "not found"})

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode()
                if self.path == "/api/accounts/oauth/token":
                    form = {k: v[0] for k, v in parse_qs(raw).items()}
                    self._json(*fake._token_reply(form))
                elif self.path == "/api/accounts/oauth/revoke":
                    if fake.revocation_down:
                        self._json(503, {"error": "unavailable"})
                        return
                    form = {k: v[0] for k, v in parse_qs(raw).items()}
                    fake.revocations.append(form)
                    fake.revoked_refresh.add(form.get("token", ""))
                    self._json(200, {})
                elif self.path == "/v1/responses":
                    if not self._authorized():
                        return
                    fake.answers.append(json.loads(raw))
                    events = [
                        {"type": "response.output_text.delta", "delta": "Hi"},
                        {
                            "type": "response.completed",
                            "response": {"status": "completed"},
                        },
                    ]
                    body = "".join(
                        f"data: {json.dumps(e)}\n\n" for e in events
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self._json(404, {"detail": "not found"})

            def _authorized(self) -> bool:
                token = (self.headers.get("Authorization") or "").removeprefix(
                    "Bearer "
                )
                if token in fake.live_access:
                    return True
                self._json(
                    401, {"error": {"code": "invalid_token", "message": "expired"}}
                )
                return False

            def _json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
