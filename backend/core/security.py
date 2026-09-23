"""Security dependencies and utilities for API authentication."""

import logging
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)


def verify_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[str]:
    """Validates the Authorization Bearer token against API_AUTH_TOKEN in settings.

    If API_AUTH_TOKEN is not configured (empty string), authentication is bypassed
    for local development and demo testing.
    """
    expected_token = settings.API_AUTH_TOKEN.strip()
    if not expected_token:
        # Development / demo mode: No auth token enforced
        return None

    if not credentials or not credentials.credentials:
        logger.warning("Unauthorized access attempt: Missing Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != expected_token:
        logger.warning("Unauthorized access attempt: Invalid Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
