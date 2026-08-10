"""
Document management endpoints
"""
from uuid import UUID
import time
from fastapi import APIRouter, UploadFile, File
from app.api.dependencies import get_vectore_storage_retrieval
from app.schemas import FileUploadResult, BatchUploadResponse, UploadStatus
import logging
from typing import List

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)

@router.post("", response_model=FileUploadResult)
async def ingest_document(
    file: UploadFile = File(...),
    domain: str = "general"
):
    """
    Upload and ingest a document.

    Supported formats: .txt, .md, .pdf, .docx

    Process:
    1. Upload original file to MinIO (preserved forever)
    2. Parse document (extract text + metadata)
    3. Chunk text into smaller pieces
    4. Generate embeddings
    5. Store in PostgreSQL with pgvector

    Returns:
    - Document ID (UUID)
    - Processing statistics
    - Extracted metadata (pages, author, etc.)
    """
    vector_storage_retrieval = get_vectore_storage_retrieval()
    if vector_storage_retrieval is None:
        raise

    return await vector_storage_retrieval.process_single_file(
        file=file,
        domain_name=domain,
        file_number=1,
        total_files=1
    )

@router.post("/batch", response_model=BatchUploadResponse)
async def batch_ingest_document(
    files: List[UploadFile] = File(...,description="Multiple files to upload (max 20)"),
    domain: str = "general"
):
    """
    Upload and ingest MULTIPLE documents in one request.

    Features:
    - Upload up to 20 files simultaneously
    - Parallel processing (faster than sequential uploads)
    - Individual error handling (one failure doesn't stop others)
    - Duplicate detection per file
    - Detailed results for each file

    Supported formats: .txt, .md, .pdf, .docx

    Returns:
    - Summary statistics (total, successful, failed, duplicates)
    - Individual results for each file with document IDs
    - Total processing time
    """
    vector_storage_retrieval = get_vectore_storage_retrieval()
    if vector_storage_retrieval is None:
        raise
    
    # Validate inputs
    MAX_FILES = 20
    if len(files) > MAX_FILES:
        raise
    
    
    # Start timing
    batch_start_time = time.time()

    # Process files concurrently
    results = await vector_storage_retrieval.process_files_concurrently(
        files=files,
        domain_name=domain
    )

    # Calculate statistics
    total_processing_time = time.time() - batch_start_time

    stats = {
        "successful": sum(1 for r in results if r.status == UploadStatus.SUCCESS),
        "failed": sum(1 for r in results if r.status == UploadStatus.FAILED),
        "duplicates": sum(1 for r in results if r.status == UploadStatus.DUPLICATE)
    }

    # Generate summary message
    if stats["successful"] == len(files):
        message = f"All {len(files)} files uploaded successfully"
    elif stats["failed"] == len(files):
        message = f"All {len(files)} files failed to upload"
    else:
        message = (
            f"Batch upload completed: {stats['successful']} successful, "
            f"{stats['failed']} failed, {stats['duplicates']} duplicates"
        )
    
    logger.info(
        f"Batch upload complete: {stats['successful']}/{len(files)} successful "
        f"in {total_processing_time:.2f}s"
    )

    return BatchUploadResponse(
        message=message,
        total_files=len(files),
        successful=stats["successful"],
        failed=stats["failed"],
        duplicates=stats["duplicates"],
        total_processing_time=total_processing_time,
        results=results
    )