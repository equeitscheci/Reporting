"""Token broker for the ECI AI Studio browser widget."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


def get_widget_access_token() -> str:
    """Return an access token for the AI Studio widget.

    Production should configure ai_widget_token_url/client_id/client_secret so the backend performs
    the token exchange. ai_widget_access_token exists only to unblock local demos.
    """

    if settings.ai_widget_access_token:
        return settings.ai_widget_access_token

    if not (
        settings.ai_widget_token_url
        and settings.ai_widget_client_id
        and settings.ai_widget_client_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ECI AI widget token broker is not configured. Set "
                "INSIGHTFORGE_AI_WIDGET_TOKEN_URL, INSIGHTFORGE_AI_WIDGET_CLIENT_ID, and "
                "INSIGHTFORGE_AI_WIDGET_CLIENT_SECRET, or set INSIGHTFORGE_AI_WIDGET_ACCESS_TOKEN "
                "for local demos."
            ),
        )

    payload: dict[str, Any] = {
        "grant_type": "client_credentials",
        "client_id": settings.ai_widget_client_id,
        "client_secret": settings.ai_widget_client_secret,
    }
    if settings.ai_widget_scope:
        payload["scope"] = settings.ai_widget_scope
    if settings.ai_widget_audience:
        payload["audience"] = settings.ai_widget_audience

    try:
        with httpx.Client(timeout=settings.ai_widget_timeout_seconds) as client:
            response = client.post(str(settings.ai_widget_token_url), data=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ECI AI widget token exchange failed: {exc}",
        ) from exc

    access_token = body.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ECI AI widget token exchange did not return access_token.",
        )

    return access_token
