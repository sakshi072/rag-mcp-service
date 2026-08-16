"""
Core configuration and security
"""
from app.core.settings import settings
from app.core.middleware import TracingMiddleware
from app.core.security import (
    verify_jwt,
    require_scope,
    extract_scopes,
    has_scope,
    validate_jwt_token
)

__all__ = [
    "verify_jwt",
    "require_scope",
    "extract_scopes",
    "has_scope",
    "validate_jwt_token",
    "settings",
    "TracingMiddleware"
]
