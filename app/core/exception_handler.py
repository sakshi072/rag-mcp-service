from fastapi import HTTPException, Request, status
import logging
from fastapi.responses import JSONResponse
from app.schemas import ErrorResponse
from pydantic import ValidationError
from fastapi.exceptions import RequestValidationError
from typing import Union
from app.core.exceptions import RetrievalBaseException
from app.core.settings import settings
import traceback

logger = logging.getLogger(__name__)

def get_request_id(request:Request) -> str:
     """Extract request ID from request state"""
     return getattr(request.state, "request_id", "unknown")

def sanitize_error_details(details:dict, is_production:bool = None) -> dict:
    """Remove sensitive information error details."""
    if is_production is None:
         is_production = settings.env == "production"
 
    if not is_production:
         return details
    
    keywords = {"password", "jwt", "token", "api_key", "access_token", "refresh_token"}
    
    return {
         k:v for k, v in details.items()
         if k.lower() not in keywords
    }

def should_log_traceback(status_code: int) -> bool:
    """Determine if full traceback should be logged"""
    # Log full traceback for 5xx errors, not for 4xx (client errors)
    return status_code >= 500

async def retrieval_exception_handler(request: Request, exc:Exception):
    """
    Handler for all custom Retrieval exceptions.
    """
    request_id = get_request_id(request)

    if should_log_traceback(exc.status_code):
        logger.error(
            f"[{request_id}] {exc.error_code}: {exc.message}",
            extra={
                "request_id": request_id,
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": request.url.path,
                "method": request.method
            },
            exc_info=True
        )
    else:
         logger.warning(
              f"[{request_id}] {exc.error_code}: {exc.message}",
              extra={
                   "request_id":request_id,
                   "error_code": exc.error_code,
                   "details": exc.details
              }
         )

    detail = sanitize_error_details(exc.details) if exc.details else {}
    detail["request_id"] = request_id
    detail["error_code"] = exc.error_code

    error_response = ErrorResponse(
         error = exc.status_code,
         message=exc.message,
         detail=detail if detail else None
    )

    return JSONResponse(
         status_code=exc.status_code,
         content=error_response.model_dump(exclude_none=True)
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handler for FastAPI HTTP exceptions
    """
    request_id = get_request_id(request)

    logger.warning(
        f"[{request_id}] HTTP {exc.status_code}: {exc.detail}",
        extra={
            "request_id":request_id,
            "status_code":exc.status_code,
            "path": request.url.path,
            "method":request.method
        })      

    error_response = ErrorResponse(
        error=exc.status_code,
        message=str(exc.detail),
        detail={"request_id": request_id, "error_code": "HTTP_ERROR"}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True)
    )

async def validation_exception_handler(request:Request, exc: Union[RequestValidationError, ValidationError]):
    """Handle for Pydantic validation errors"""

    request_id = get_request_id(request)

    # Extract validation error
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error['msg'],
            "type": error['type']
        })

    logger.warning(
        f"[{request_id}] Validation error: {len(errors)} field(s) invalid",
        extra={
            "request_id": request_id,
            "errors": errors,
            "path":request.url.path
        }
    )

    error_response = ErrorResponse(
        error=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Request validation error",
        detail={
            "request_id":request_id,
            "error_code": "VALIDATION_ERROR",
            "errors": errors
        }
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(exclude_none=True)
    )
                                                                                         
async def general_exception_handler(request: Request, exc: Exception):
    """
    Global exception to catch all unhandled exceptions
    """
    request_id = get_request_id(request) 

    logger.critical(
        f"[{request_id}] UNHANDLED EXCEPTION: {type(exc).__name__}: {str(exc)}",
        extra={
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        },
        exc_info=True
    )

    error_response = ErrorResponse(
        error = status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred. Please try again later.",
        detail={
            "request_id":request_id,
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(exclude_none=True)
    )

# ============================================================================
# Exception Handler Registry
# ============================================================================
def register_exception_handlers(app):
    """
    Register all exception handlers with FastAPI app.
    """
    # Custom retrieval exception handler
    # Note: there's no separate handler registered for SQLAlchemyError or
    # S3Error here. Both are translated into RetrievalBaseException
    # subclasses at their source (database.py's session context manager for
    # DB errors, document_storage.py for MinIO errors) before they can ever
    # reach this middleware, so a single handler on the base class covers
    # every case via FastAPI's MRO-based exception lookup. 
    app.add_exception_handler(RetrievalBaseException, retrieval_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    logger.info("Exception handler registered successfully")