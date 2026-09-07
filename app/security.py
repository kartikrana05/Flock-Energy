from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

# Returned as the caller identity when AUTH_ENABLED=false, so downstream code
# always has a subject to work with whether or not auth is switched on.
ANONYMOUS_SUBJECT = "anonymous"


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    if not settings.auth_enabled:
        return ANONYMOUS_SUBJECT

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")

    return payload["sub"]
