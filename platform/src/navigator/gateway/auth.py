"""Cognito access-token verification. The caller's identity comes ONLY from a verified token's `sub`,
never from a request body, query string or custom header."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

import jwt
from jwt import PyJWKClient

from navigator.errors import Forbidden, ServiceUnavailable, Unauthorized

_SUB = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


# Cognito names federated users "<Provider>_<id>" and puts them in an auto-created group "<poolId>_<Provider>".
_FEDERATED_USERNAME = re.compile(r"^(Google|Facebook|LoginWithAmazon|SignInWithApple)_")


@dataclass(frozen=True)
class Identity:
    sub: str
    groups: frozenset[str]
    # True when the user signed in through an external identity provider (Google). Such users prove who they are,
    # but only an administrator can approve them to use paid features. Derived from verified token claims only.
    federated: bool = False

    def is_admin(self, admin_group: str) -> bool:
        return admin_group in self.groups


class JwtVerifier:
    def __init__(self, user_pool_id: str, client_id: str, key_resolver: Callable[[str], Any] | None = None, leeway: int = 30):
        if not user_pool_id or "_" not in user_pool_id or not client_id:
            # Misconfiguration must fail CLOSED: every request is refused, none is let through.
            self._configured = False
            self.issuer = ""
        else:
            self._configured = True
            self.issuer = f"https://cognito-idp.{user_pool_id.split('_')[0]}.amazonaws.com/{user_pool_id}"
        self.pool_id = user_pool_id
        self.client_id, self.leeway = client_id, leeway
        self._resolver = key_resolver
        self._jwks = PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=3600) if self._configured and not key_resolver else None

    def _key(self, token: str) -> Any:
        if self._resolver:
            return self._resolver(token)
        assert self._jwks is not None
        return self._jwks.get_signing_key_from_jwt(token).key

    def verify(self, authorization_header: str | None) -> Identity:
        if not self._configured:
            raise ServiceUnavailable("Authentication is not configured")
        match = re.fullmatch(r"Bearer\s+([\w-]+\.[\w-]+\.[\w-]+)", (authorization_header or "").strip())
        if not match:
            raise Unauthorized("Missing or malformed bearer token")
        token = match.group(1)
        try:
            claims = jwt.decode(
                token,
                self._key(token),
                algorithms=["RS256"],  # never accept "none" or HMAC variants
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iss", "sub"], "verify_aud": False},
            )
        except jwt.exceptions.PyJWKClientConnectionError as e:
            raise ServiceUnavailable("Could not fetch signing keys") from e
        except jwt.PyJWTError as e:
            raise Unauthorized("Invalid or expired token") from e
        # Access tokens carry client_id (not aud); ID tokens must not be accepted for API access.
        if claims.get("token_use") != "access" or claims.get("client_id") != self.client_id:
            raise Unauthorized("Token was not issued for this application")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not _SUB.match(sub):
            raise Unauthorized("Invalid token subject")
        groups = claims.get("cognito:groups") or []
        group_set = frozenset(g for g in groups if isinstance(g, str)) if isinstance(groups, list) else frozenset()
        username = claims.get("username")
        federated = any(g.startswith(f"{self.pool_id}_") for g in group_set) or (isinstance(username, str) and bool(_FEDERATED_USERNAME.match(username)))
        return Identity(sub, group_set, federated)

    def require_admin(self, identity: Identity, admin_group: str) -> None:
        if not identity.is_admin(admin_group):
            raise Forbidden("Administrator access required")
