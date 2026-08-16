"""
Core configuration and security
"""
from app.core.settings import settings
from app.core.middleware import TracingMiddleware
from app.core.exception_handler import register_exception_handlers
from app.core.security import (
    verify_jwt,
    require_scope,
    extract_scopes,
    has_scope,
    validate_jwt_token
)
from app.core.exceptions import (
    RetrievalBaseException,
    DatabaseException,
    ServiceUnavailableException,
    DocumentNotFound,
    DocumentParsingException,
    DocumentTooLargeException,
    DuplicateDocumentException,
    InsufficientContentException,
    InvalidParameterException
)

__all__ = [
    "verify_jwt",
    "require_scope",
    "extract_scopes",
    "has_scope",
    "validate_jwt_token",
    "settings",
    "register_exception_handlers",
    "TracingMiddleware",
    "RetrievalBaseException",
     "DatabaseException",
    "ServiceUnavailableException",
    "DocumentNotFound",
    "DocumentParsingException",
    "DocumentTooLargeException",
    "DuplicateDocumentException",
    "InsufficientContentException",
    "InvalidParameterException"
]
