"""
The browser never calls this API directly; the SvelteKit BFF does, server to
server, presenting a shared secret. Every data route depends on this check.
"""

import os
import secrets

from fastapi import Header, HTTPException, status


def require_service_token(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("BACKEND_SERVICE_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service token not configured",
        )

    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :].strip()

    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing service token",
        )
