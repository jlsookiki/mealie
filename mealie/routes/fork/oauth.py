"""
Fork-specific routes: Mealie as an OAuth 2.0 authorization server.

Lets MCP clients (claude.ai, Claude Code, the mobile apps) connect with a real
"Log in with Mealie" flow: the authorize step is a frontend consent page
(/connect) shown to an already-logged-in Mealie session, and the access tokens
issued ARE per-user Mealie API tokens — they appear under Profile -> Manage
API Tokens and are revocable there.

Endpoints (all under /api/fork/oauth):
  POST /register        dynamic client registration (RFC 7591, anonymous)
  GET  /client/{id}     client display name for the consent page (anonymous)
  POST /authorize       mint an auth code (called by /connect, USER AUTH)
  POST /token           code/refresh -> real Mealie API token (anonymous)
  POST /revoke          revoke a token pair (anonymous, RFC 7009)

State (clients, pending codes, refresh records) lives in a small JSON file in
the data dir — secrets stored only as sha256 hashes. The heavy lifting of
access-token auth stays Mealie's own JWT machinery.
"""

import hashlib
import hmac
import json
import secrets
import time
from base64 import urlsafe_b64encode
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm.session import Session

from mealie.core.config import get_app_dirs
from mealie.core.security import create_access_token
from mealie.db.db_setup import generate_session
from mealie.repos.all_repositories import get_repositories
from mealie.routes._base import BaseUserController, controller
from mealie.routes._base.routers import UserAPIRouter
from mealie.schema.user import CreateToken

public_router = APIRouter(prefix="/fork/oauth")
user_router = UserAPIRouter(prefix="/fork/oauth")

CODE_TTL = 10 * 60                       # auth codes: 10 minutes
ACCESS_TOKEN_DAYS = 365                  # issued Mealie API tokens: 1 year
REFRESH_TTL = 180 * 24 * 60 * 60         # refresh records: 180 days
INTEGRATION_ID = "claude-mcp"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _gen(nbytes: int = 32) -> str:
    return secrets.token_hex(nbytes)


def _pkce_ok(verifier: str, challenge: str) -> bool:
    computed = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return hmac.compare_digest(computed, challenge)


class _Store:
    """JSON-file persistence for OAuth state (single household, low volume)."""

    def __init__(self) -> None:
        self.path: Path = get_app_dirs().DATA_DIR / "oauth-provider.json"
        self.data: dict[str, dict] = {"clients": {}, "codes": {}, "refresh": {}}
        try:
            self.data = {**self.data, **json.loads(self.path.read_text())}
        except Exception:
            pass

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data))
        tmp.chmod(0o600)
        tmp.replace(self.path)

    def prune(self) -> None:
        now = time.time()
        self.data["codes"] = {k: c for k, c in self.data["codes"].items() if not c["used"] and c["expires_at"] > now}
        self.data["refresh"] = {k: r for k, r in self.data["refresh"].items() if r["expires_at"] > now}
        self._persist()

    def save(self) -> None:
        self._persist()


_store = _Store()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ClientRegistration(BaseModel):
    client_name: str | None = None
    redirect_uris: list[str]
    grant_types: list[str] | None = None


class AuthorizeRequest(BaseModel):
    client_id: str
    redirect_uri: str
    state: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str | None = None


class TokenRequest(BaseModel):
    grant_type: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    code: str | None = None
    redirect_uri: str | None = None
    code_verifier: str | None = None
    refresh_token: str | None = None


async def _request_params(request: Request) -> dict:
    """OAuth token/revoke requests arrive form-encoded per RFC 6749 (what
    claude.ai sends); JSON is accepted too for convenience. Unknown fields
    (scope, resource, ...) are carried through and ignored by the models."""
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            return await request.json()
        except Exception:
            return {}
    try:
        form = await request.form()
        return {k: str(v) for k, v in form.items()}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Anonymous endpoints
# ---------------------------------------------------------------------------


def _oauth_error(status_code: int, error: str, description: str) -> HTTPException:
    return HTTPException(status_code, {"error": error, "error_description": description})


@public_router.post("/register", status_code=201)
def register_client(body: ClientRegistration) -> dict:
    if not body.redirect_uris:
        raise _oauth_error(400, "invalid_request", "redirect_uris required")
    _store.prune()
    client_id = _gen(16)
    client_secret = _gen()
    grant_types = body.grant_types or ["authorization_code", "refresh_token"]
    _store.data["clients"][client_id] = {
        "client_id": client_id,
        "client_secret_hash": _hash(client_secret),
        "client_name": body.client_name,
        "redirect_uris": body.redirect_uris,
        "grant_types": grant_types,
        "created_at": time.time(),
    }
    _store.save()
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_name": body.client_name,
        "redirect_uris": body.redirect_uris,
        "grant_types": grant_types,
        "token_endpoint_auth_method": "client_secret_post",
    }


@public_router.get("/client/{client_id}")
def client_info(client_id: str) -> dict:
    client = _store.data["clients"].get(client_id)
    if not client:
        raise _oauth_error(404, "invalid_client", "Unknown client_id")
    return {"client_id": client_id, "client_name": client.get("client_name")}


def _issue_tokens(session: Session, user_id: str, client: dict) -> dict:
    """Mint a REAL Mealie API token for the user (visible/revocable in their
    profile) plus a rotating refresh record."""
    client_name = client.get("client_name") or "MCP client"
    token_name = f"{client_name} (OAuth)"
    token = create_access_token(
        {"long_token": True, "id": user_id, "name": token_name, "integration_id": INTEGRATION_ID},
        timedelta(days=ACCESS_TOKEN_DAYS),
    )
    repos = get_repositories(session, group_id=None, household_id=None)
    token_db = repos.api_tokens.create(CreateToken(name=token_name, token=token, user_id=user_id))

    refresh = _gen()
    _store.data["refresh"][_hash(refresh)] = {
        "user_id": user_id,
        "client_id": client["client_id"],
        "token_db_id": token_db.id,
        "expires_at": time.time() + REFRESH_TTL,
    }
    _store.save()
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_DAYS * 24 * 60 * 60,
        "refresh_token": refresh,
        "scope": "mealie",
    }


def _delete_api_token(session: Session, token_db_id: Any) -> None:
    repos = get_repositories(session, group_id=None, household_id=None)
    try:
        repos.api_tokens.delete(token_db_id)
    except Exception:
        pass  # already deleted by the user in their profile — fine


@public_router.post("/token")
async def token_grant(request: Request, session: Session = Depends(generate_session)) -> dict:
    params = await _request_params(request)
    body = TokenRequest(**{k: params.get(k) for k in TokenRequest.model_fields})
    _store.prune()
    client = _store.data["clients"].get(body.client_id or "")
    if not client:
        raise _oauth_error(400, "invalid_client", "Unknown client_id")
    if body.client_secret and not hmac.compare_digest(_hash(body.client_secret), client["client_secret_hash"]):
        raise _oauth_error(400, "invalid_client", "Bad client_secret")

    if body.grant_type == "authorization_code":
        if not body.code or not body.redirect_uri:
            raise _oauth_error(400, "invalid_request", "code and redirect_uri required")
        ac = _store.data["codes"].get(_hash(body.code))
        if not ac or ac["used"] or ac["expires_at"] < time.time():
            raise _oauth_error(400, "invalid_grant", "code invalid, used, or expired")
        if ac["redirect_uri"] != body.redirect_uri or ac["client_id"] != body.client_id:
            raise _oauth_error(400, "invalid_grant", "redirect_uri/client_id mismatch")
        if ac["code_challenge"] and not (body.code_verifier and _pkce_ok(body.code_verifier, ac["code_challenge"])):
            raise _oauth_error(400, "invalid_grant", "PKCE verification failed")
        ac["used"] = True
        _store.save()
        return _issue_tokens(session, ac["user_id"], client)

    if body.grant_type == "refresh_token":
        rec = _store.data["refresh"].pop(_hash(body.refresh_token or ""), None)
        if not rec or rec["client_id"] != body.client_id or rec["expires_at"] < time.time():
            _store.save()
            raise _oauth_error(400, "invalid_grant", "refresh token invalid")
        _delete_api_token(session, rec["token_db_id"])  # rotate the Mealie token
        _store.save()
        return _issue_tokens(session, rec["user_id"], client)

    raise _oauth_error(400, "unsupported_grant_type", str(body.grant_type))


@public_router.post("/revoke")
async def revoke(request: Request, session: Session = Depends(generate_session)) -> dict:
    params = await _request_params(request)
    token = str(params.get("token") or "")
    if token:
        rec = _store.data["refresh"].pop(_hash(token), None)
        if rec:
            _delete_api_token(session, rec["token_db_id"])
            _store.save()
    return {}


# ---------------------------------------------------------------------------
# Authenticated approve (called by the /connect consent page)
# ---------------------------------------------------------------------------


@controller(user_router)
class ForkOAuthAuthorizeController(BaseUserController):
    @user_router.post("/authorize")
    def approve(self, body: AuthorizeRequest) -> dict:
        """The logged-in user approved the consent page: mint an auth code and
        return the redirect URL to send the client back to."""
        _store.prune()
        client = _store.data["clients"].get(body.client_id)
        if not client:
            raise _oauth_error(400, "invalid_client", "Unknown client_id")
        if body.redirect_uri not in client["redirect_uris"]:
            raise _oauth_error(400, "invalid_request", "redirect_uri not registered")

        code = _gen()
        _store.data["codes"][_hash(code)] = {
            "client_id": body.client_id,
            "redirect_uri": body.redirect_uri,
            "code_challenge": body.code_challenge or None,
            "user_id": str(self.user.id),
            "expires_at": time.time() + CODE_TTL,
            "used": False,
        }
        _store.save()

        sep = "&" if "?" in body.redirect_uri else "?"
        url = f"{body.redirect_uri}{sep}code={code}"
        if body.state:
            url += f"&state={body.state}"
        return {"redirect_url": url}
