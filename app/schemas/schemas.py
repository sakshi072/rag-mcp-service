"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class IngestRequest(BaseModel):
    """Request schema for document ingestion (placeholder for metadata)."""
    pass


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================
 
class UploadStatus(str, Enum):
    """Status of individual file upload"""
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    SKIPPED = "skipped"

class FileUploadResult(BaseModel):
    """Response schema for document ingestion."""

    message: Optional[str] = Field(None, description="Status message")
    filename: str = Field(..., description="Uploaded filename")
    status: UploadStatus = Field(..., description="Status of uploaded file")
    document_id: Optional[str] = Field(None, description="Document UUID")
    chunks_created: Optional[int] = Field(None, description="Number of chunks created")
    processing_time: float = Field(..., description="Processing time in seconds")
    error_message: Optional[str] = Field(None, description="Error message (if failed)")
    metadata: Optional[dict] = Field(None, description="Document metadata (pages, format, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Document ingested successfully",
                "filename": "ml_basics.txt",
                "status": "success",
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "chunks_created": 15,
                "processing_time": 3.2,
                "error_message": None,
                "metadata": {
                    "pages": 5,
                    "format": "pdf",
                    "file_size": 204800
                },
                
            }
        }

class BatchUploadResponse(BaseModel):
    """Response for batch file upload"""
    message: str = Field(..., description="Overall status message")
    total_files: int = Field(..., description="Total files submitted")
    successful: int = Field(..., description="Number of successful uploads")
    failed: int = Field(..., description="Number of failed uploads")
    duplicates: int = Field(..., description="Number of duplicate files detected")
    total_processing_time: float = Field(..., description="Total time in seconds")
    results: List[FileUploadResult] = Field(..., description="Individual file results")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Batch upload completed",
                "total_files": 5,
                "successful": 3,
                "failed": 1,
                "duplicates": 1,
                "total_processing_time": 15.7,
                "results": [
                    {
                        "filename": "doc1.pdf",
                        "status": "success",
                        "document_id": "123e4567-e89b-12d3-a456-426614174000",
                        "chunks_created": 42,
                        "processing_time": 3.2,
                        "error_message": None
                    },
                    {
                        "filename": "doc2.pdf",
                        "status": "duplicate",
                        "document_id": "existing-id",
                        "chunks_created": 30,
                        "processing_time": 0.1,
                        "error_message": None
                    },
                    {
                        "filename": "doc3.txt",
                        "status": "failed",
                        "document_id": None,
                        "chunks_created": None,
                        "processing_time": 1.5,
                        "error_message": "Unsupported file type"
                    }
                ]
            }
        }

class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall status")
    components: dict = Field(..., description="Component statuses")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "components": {
                    "vector_storage_and_retrieval System": "ok",
                    "postgres": "ok",
                    "minio": "ok",
                    "llm": "ok"
                }
            }
        }


class StatResponse(BaseModel):
    """Statistics response"""

    total_documents: int = Field(..., description="Total documents in system")
    total_chunks: int = Field(..., description="Total chunks in system")
    status_breakdown: Dict[str, int] = Field(
        ...,
        description="Documents by status"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 42,
                "total_chunks": 1337,
                "status_breakdown": {
                    "completed": 40,
                    "processing": 1,
                    "failed": 1
                }
            }
        }