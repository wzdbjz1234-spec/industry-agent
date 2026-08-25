"""Minimal OIDC userinfo adapter with no provider SDK dependency."""

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx

from quality_case_agent.application.ports.identity import IdentityAuthenticationError
from quality_case_agent.contracts.identity import IdentityContract, Role


class OidcIdentityAdapter:
    def __init__(
        self,
        userinfo_url: str,
        *,
        client: httpx.Client | None = None,
        clock: object | None = None,
        ttl: timedelta = timedelta(minutes=10),
    ) -> None:
        self._userinfo_url = userinfo_url
        self._client = client or httpx.Client(timeout=5.0)
        self._clock = clock
        self._ttl = ttl

    def authenticate(self, headers: Mapping[str, str]) -> IdentityContract:
        authorization = headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer "):
            raise IdentityAuthenticationError("OIDC bearer token is required")
        token = authorization[7:].strip()
        if not token:
            raise IdentityAuthenticationError("OIDC bearer token is empty")
        try:
            response = self._client.get(
                self._userinfo_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            claims: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IdentityAuthenticationError("OIDC userinfo request failed") from exc
        if not isinstance(claims, dict):
            raise IdentityAuthenticationError("OIDC claims must be an object")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise IdentityAuthenticationError("OIDC subject is missing")
        roles = self._roles(claims)
        now = self._now()
        organization = str(claims.get("organization") or claims.get("org") or "unknown")
        actor_id = str(claims.get("preferred_username") or claims.get("email") or subject)
        digest = hashlib.sha256(
            json.dumps(claims, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return IdentityContract(
            actor_id=actor_id,
            subject=subject,
            roles=roles,
            organization=organization,
            auth_source="OIDC",
            claims_digest=digest,
            issued_at=now,
            expires_at=now + self._ttl,
        )

    def _now(self) -> datetime:
        if callable(self._clock):
            value = self._clock()
            if isinstance(value, datetime):
                return value.astimezone(UTC)
        return datetime.now(UTC)

    @staticmethod
    def _roles(claims: dict[str, object]) -> list[Role]:
        raw: object = claims.get("roles", [])
        if not raw and isinstance(claims.get("realm_access"), dict):
            realm_access = claims["realm_access"]
            if isinstance(realm_access, dict):
                raw = realm_access.get("roles", [])
        if isinstance(raw, str):
            raw = raw.replace(",", " ").split()
        if not isinstance(raw, list):
            raise IdentityAuthenticationError("OIDC roles claim is invalid")
        valid = {"VIEWER", "QUALITY_ENGINEER", "APPROVER", "OPERATOR", "ADMIN"}
        roles = [str(item).upper() for item in raw if str(item).upper() in valid]
        if not roles:
            raise IdentityAuthenticationError("OIDC roles claim has no supported role")
        return cast(list[Role], list(dict.fromkeys(roles)))
