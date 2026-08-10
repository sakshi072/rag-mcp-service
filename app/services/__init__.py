"""
Business logic services
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from app.db import db_manager
from app.services.ingestion_service import IngestionService
from app.schemas import FileUploadResult
from cachetools import TTLCache
from fastapi import UploadFile
logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Facade combining ingestion and search services.

    Provides backward-compatible interface for existing API code.
    """

    def __init__(self) -> None:
        """Initialize both services."""
        logger.info("Initializing KnowledgeBase...")

        self._ingestion = IngestionService()

        # Initialize database
        db_manager.initialize()

        logger.info("KnowledgeBase ready\n")

    # =========================================================================
    # Ingestion (delegated)
    # =========================================================================

    async def process_single_file(
            self,
            file:UploadFile,
            domain_name:str,
            file_number:int,
            total_files:int
    ) -> FileUploadResult:
        """Process single file"""
        return await self._ingestion.process_single_file(
            file=file,
            domain=domain_name,
            file_number=file_number,
            total_files=total_files,
        )
    
    async def process_files_concurrently(
        self,
        files: List[UploadFile],
        domain_name:str
    ) -> List[FileUploadResult]:
        """
        Process batch upload with Pre-Flight Domain Resolution.
        Ensures the domain is locked/created before parallel workers start.
        """

        logger.info(f"Batch Processing {len(files)} files for domain: {domain_name}")

        try:
            async with db_manager.session() as session:
                await self._ingestion.ensure_domain(session, domain_name)
                await session.commit()
            logger.info(f"Domain '{domain_name} resolved.")
        except Exception as e:
            logger.error(f"Failed to resolve domain '{domain_name} during pre-flight: {e}")
            
        return await self._ingestion.process_files_concurrently(
            files,
            domain_name
        )
    
    async def ingest_file(
        self,
        file_data: bytes,
        filename: str,
        file_type: str,
        domain_name: str = "general",
        owner_id: Optional[str] = None,
        is_public: bool = False,
        metadata: Optional[Dict] = None,
    ) -> tuple[UUID, bool]:
        """Ingest document with chunking and embedding."""
        return await self._ingestion.ingest_file(
            file_data=file_data,
            filename=filename,
            file_type=file_type,
            domain_name=domain_name,
            owner_id=owner_id,
            is_public=is_public,
            metadata=metadata,
        )

    async def get_stats(self) -> Dict:
        """Get system statistics."""
        return await self._ingestion.get_stats()


__all__ = [
    "KnowledgeBase",
    "IngestionService",
]
