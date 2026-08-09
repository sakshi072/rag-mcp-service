"""
FastAPI REST API for Vector Storage and Retrieval System

Run: uvicorn app.main:app --reload
Access: http://localhost:8001/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.db import startup_database, shutdown_database
from app.utils.document_storage import storage_service
from app.core.middleware import TracingMiddleware
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

# ============================================================================
# Lifespan Context Manager
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    logger.info("Starting Vector Storage and Retrieval API...")

    try:
        # Initialize database
        await startup_database()

        # Initialize minIO
        storage_service._ensure_bucket_exists()
        logger.info("MinIO Bucket verified on startup.")

        logger.info("Vector Storage and Retrieval system initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize Vector Storage and Retrieval system: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Vector Storage and Retrieval API...")
    await shutdown_database()
    logger.info("Shutdown complete")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Vector Storage and Retrieval API",
    description="Semantic search Vector Storage and Retrieval system with document upload and querying and OAuth 2.0 authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(TracingMiddleware)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "database": "connected"}
