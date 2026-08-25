"""Identity provider and authorization seams."""

from collections.abc import Mapping
from typing import Protocol

from quality_case_agent.contracts.identity import IdentityContract


class IdentityAuthenticationError(ValueError):
    """The caller did not provide a valid identity context."""


class IdentityProvider(Protocol):
    def authenticate(self, headers: Mapping[str, str]) -> IdentityContract:
        """Resolve request headers into a validated identity without leaking provider SDKs."""


class AuthorizationPolicy(Protocol):
    def authorize(self, identity: IdentityContract, action: str) -> None:
        """Raise ``PermissionError`` when the identity cannot perform an action."""
