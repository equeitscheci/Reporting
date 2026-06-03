"""RBAC + tenant-scoped auth dependency for the API.

In production this validates an OIDC JWT (Auth0/Cognito) and extracts tenant + roles. In dev,
`auth_disabled` short-circuits to a synthetic principal so the API is usable without an IdP.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import settings


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# Capability matrix: which roles may perform which actions.
PERMISSIONS: dict[str, set[Role]] = {
    "config:read": {Role.OWNER, Role.ADMIN, Role.ANALYST, Role.VIEWER},
    "config:write": {Role.OWNER, Role.ADMIN},
    "data:read": {Role.OWNER, Role.ADMIN, Role.ANALYST, Role.VIEWER},
    "pipeline:run": {Role.OWNER, Role.ADMIN, Role.ANALYST},
    "insights:read": {Role.OWNER, Role.ADMIN, Role.ANALYST, Role.VIEWER},
}


@dataclass
class Principal:
    user_id: str
    tenant_id: str
    roles: list[Role]

    def can(self, action: str) -> bool:
        allowed = PERMISSIONS.get(action, set())
        return any(r in allowed for r in self.roles)

    def require(self, action: str) -> None:
        if not self.can(action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission for action '{action}'",
            )


def get_principal(
    x_tenant_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_roles: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Principal:
    """FastAPI dependency producing the authenticated, tenant-scoped principal."""

    if settings.auth_disabled:
        return Principal(
            user_id=x_user_id or "dev-user",
            tenant_id=x_tenant_id or "acme-mfg",
            roles=_parse_roles(x_roles) or [Role.OWNER],
        )

    # Production path: validate JWT, extract claims. (IdP integration is Phase 1 infra work.)
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    claims = _verify_jwt(authorization)
    return Principal(
        user_id=claims["sub"],
        tenant_id=claims["tenant_id"],
        roles=_parse_roles(",".join(claims.get("roles", []))) or [Role.VIEWER],
    )


def _parse_roles(raw: str | None) -> list[Role]:
    if not raw:
        return []
    out = []
    for token in raw.split(","):
        token = token.strip().lower()
        try:
            out.append(Role(token))
        except ValueError:
            continue
    return out


def _verify_jwt(authorization: str) -> dict:  # pragma: no cover - infra
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="JWT verification is wired to the IdP at deploy time",
    )
