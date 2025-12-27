"""Simple session-based authentication"""
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from backend.common.config import config
from backend.common.logging_config import get_logger

logger = get_logger(__name__)

# Session serializer
serializer = URLSafeTimedSerializer(config.SESSION_SECRET)

# Session cookie name
SESSION_COOKIE_NAME = "palworld_lens_session"

# Session max age (7 days in seconds)
SESSION_MAX_AGE = 7 * 24 * 60 * 60


def create_session_token(username: str) -> str:
    """Create a signed session token"""
    return serializer.dumps(username)


def verify_session_token(token: str) -> Optional[str]:
    """Verify a session token and return username if valid"""
    try:
        username = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return username
    except (BadSignature, SignatureExpired):
        return None


def get_session_from_request(request: Request) -> Optional[str]:
    """Extract and verify session from request cookies"""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return verify_session_token(token)


def verify_credentials(username: str, password: str) -> bool:
    """Verify username and password against config"""
    return username == config.USERNAME and password == config.PASSWORD


async def require_auth(request: Request):
    """Dependency to require authentication on endpoints"""
    # Skip auth if login is disabled
    if not config.ENABLE_LOGIN:
        return
    
    # Check for valid session
    username = get_session_from_request(request)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
