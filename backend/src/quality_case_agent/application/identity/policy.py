"""Application-side role policy; frontend visibility is never an authorization control."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar, cast

from quality_case_agent.application.ports.identity import (
    IdentityAuthenticationError,
)
from quality_case_agent.contracts.identity import AuthSource, IdentityContract, Role


class AuthorizationDenied(PermissionError):
    """The authenticated identity lacks the required role."""


class IdentityPolicy:
    """Small, explicit policy table for mutating and sensitive operations."""

    _ROLE_RULES: ClassVar[dict[str, frozenset[Role]]] = {
        "proposal.read": frozenset({"VIEWER", "QUALITY_ENGINEER", "APPROVER", "OPERATOR", "ADMIN"}),
        "proposal.decide": frozenset({"APPROVER", "ADMIN"}),
        "qms.retry": frozenset({"OPERATOR", "ADMIN"}),
        "qms.shadow": frozenset({"QUALITY_ENGINEER", "APPROVER", "OPERATOR", "ADMIN"}),
        "audit.read": frozenset({"APPROVER", "OPERATOR", "ADMIN"}),
        "audit.export": frozenset({"ADMIN"}),
    }
    version = "identity-policy-v1"

    def authorize(self, identity: IdentityContract, action: str) -> None:
        allowed = self._ROLE_RULES.get(action)
        if allowed is None:
            raise AuthorizationDenied(f"unknown protected action: {action}")
        if not allowed.intersection(identity.roles):
            raise AuthorizationDenied(
                f"actor {identity.actor_id} is not authorized for {action}"
            )


def system_identity(
    actor_id: str,
    *,
    role: Role = "OPERATOR",
    organization: str = "system",
) -> IdentityContract:
    """Create a short-lived, explicit identity for an internal audited action."""

    now = datetime.now(UTC)
    claims = {"actor_id": actor_id, "roles": [role], "organization": organization, "auth_source": "SYSTEM"}
    return IdentityContract(
        actor_id=actor_id,
        subject=actor_id,
        roles=[role],
        organization=organization,
        auth_source="SYSTEM",
        claims_digest=HeaderIdentityProvider._digest(claims),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )


@dataclass(frozen=True, slots=True)
class HeaderIdentityProvider:
    """Demo/test identity adapter; production should use the OIDC adapter."""

    required: bool = False
    default_actor_id: str = "demo-quality-engineer"
    default_role: Role = "APPROVER"
    default_organization: str = "demo-plant"
    clock: object | None = None

    def authenticate(self, headers: Mapping[str, str]) -> IdentityContract:
        actor_id = headers.get("X-Actor-Id", "").strip()
        if not actor_id and headers.get("X-Operator-Id", "").strip():
            actor_id = headers["X-Operator-Id"].strip()
            headers = {**headers, "X-Actor-Role": "OPERATOR"}
        role_value = headers.get("X-Actor-Role", "").strip().upper()
        organization = headers.get("X-Organization", self.default_organization).strip()
        auth_source: AuthSource = "DEMO"
        if not actor_id:
            if self.required:
                raise IdentityAuthenticationError("X-Actor-Id is required")
            actor_id = self.default_actor_id
            role_value = self.default_role
            auth_source = "DEMO"
        else:
            auth_source = "SYSTEM" if actor_id.startswith("system:") else "DEMO"
        roles = self._roles(role_value or self.default_role)
        now = self._now()
        claims: dict[str, object] = {
            "actor_id": actor_id,
            "roles": roles,
            "organization": organization,
            "auth_source": auth_source,
        }
        return IdentityContract(
            actor_id=actor_id,
            subject=headers.get("X-Subject", actor_id),
            roles=roles,
            organization=organization or self.default_organization,
            auth_source=auth_source,
            claims_digest=self._digest(claims),
            issued_at=now,
            expires_at=now + timedelta(hours=1),
        )

    def _now(self) -> datetime:
        if callable(self.clock):
            value = self.clock()
            if isinstance(value, datetime):
                return value.astimezone(UTC)
        return datetime.now(UTC)

    @staticmethod
    def _roles(value: str) -> list[Role]:
        valid = {"VIEWER", "QUALITY_ENGINEER", "APPROVER", "OPERATOR", "ADMIN"}
        roles = [item.strip().upper() for item in value.replace(",", " ").split() if item.strip()]
        selected = [item for item in roles if item in valid]
        if not selected:
            raise IdentityAuthenticationError("no valid role in identity headers")
        return cast(list[Role], list(dict.fromkeys(selected)))

    @staticmethod
    def _digest(claims: Mapping[str, object]) -> str:
        canonical = json.dumps(claims, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
