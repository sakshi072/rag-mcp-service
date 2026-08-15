"""
Search Service

Handles:
- Semantic search with vector similarity
- Optional reranking
"""

import logging
import time
from typing import Dict, List, Optional
from uuid import UUID

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from app.db import DocumentChunk, Domain, db_manager, SearchAnalytics
from app.utils.embeddings import get_shared_embedder, embed_chunks
from app.utils.reranking_strategy import (
    RerankCandidate,
    RerankerConfig,
    RerankStrategy,
    UnifiedReranker,
)
from app.utils.redis_cache_helper import SearchCache
from app.schemas import SearchResult
from app.core.settings import settings

logger = logging.getLogger(__name__)

class SearchService:
    """Service for search and document retrieval operations."""

    def __init__(self) -> None:
        """Initialize the search service."""
        logger.info("Initializing SearchService...")

        # Load config
        self.embedding_model = settings.embedding.model

        # Load embedder (shared with ingestion service)
        logger.info(f"  Embedding model: {self.embedding_model}")
        self.embedder = get_shared_embedder(self.embedding_model)

        # Initialize reranker if enabled
        self.reranker: Optional[UnifiedReranker] = None

        logger.info("SearchService ready")

    # =========================================================================
    # Search
    # =========================================================================
    
    async def search(
        self,
        query_text: str,
        top_k: int = 5,
        domain_name: Optional[str] = None,
        rerank_strategy: RerankStrategy = RerankStrategy.COMBINED,
    ) -> Dict:
        """
        Search with vector similarity and optional reranking.

        Args:
            query_text: User's query
            domain_name: Filter by domain (None = all domains)
            top_k: Number of results to return
            rerank_strategy: Reranking strategy to use

        Returns:
            Dictionary with sources and metadata
        """
        start_time = time.time()
        logger.info(f"Search: {query_text[:50]}...")
        
        async with db_manager.session() as session:
            
            domain_id = None

            # Get domain config if domain name
            if domain_name:
                logger.info(f"  Domain: {domain_name}")

                domain_id = await self._resolve_domain(
                    session, domain_name
                )

                # If domain name was provided but doesn't exist, return empty
                if not domain_id:
                    logger.warning(f"History requested for unknown domain: {domain_name}")
                    return {}

            # Generate query embedding
            logger.info("  1/3 Generating query embedding...")
            query_embedding = (await embed_chunks(
                [query_text],
                self.embedding_model
            ))[0]
           
            # Vector search
            use_reranking = True
            fetch_limit = (
                top_k * 3
                if use_reranking
                else top_k
            )

            logger.info("  2/3 Searching vector database...")
            candidates = await self._vector_search(
                session=session,
                query_embedding=query_embedding,
                domain_id=domain_id,
                domain_name=domain_name,
                limit=fetch_limit,
            )

            if not candidates:
                return {
                    "sources": [],
                    "query_time": round(time.time() - start_time, 2),
                    "domain": domain_name,
                    "message": "No results found",
                }

            logger.info(f"      Found {len(candidates)} candidates")

            # Rerank or return directly
            if use_reranking and self.reranker:
                logger.info(f"  3/3 Reranking ({rerank_strategy.value})...")
                self.reranker.config.strategy = rerank_strategy
                final_results = self.reranker.rerank(
                    candidates=candidates,
                    query_text=query_text,
                    query_embedding=query_embedding,
                    top_k=top_k,
                )
                strategy_used = rerank_strategy.value

            else:
                logger.info(f"  3/3 Returning top {top_k} by similarity")
                final_results = [
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "domain": c.domain,
                        "text": c.text,
                        "similarity": c.vector_similarity,
                        "file_url": c.file_url,
                        "chunk_index": c.chunk_index,
                        "page_number": c.page_number,
                    }
                    for c in candidates[:top_k]
                ]
                strategy_used = "none"

            query_time = time.time() - start_time
            logger.info(f"Search complete: {query_time:.2f}s, {len(final_results)} results")

            search_analytics = SearchAnalytics(
                query_text = query_text,
                result_chunk_ids = [item["chunk_id"] for item in final_results],
                similarity_scores = [item["similarity"] for item in final_results],
                embedding_time_ms = 0,
                search_time_ms = 0,
                total_processing_time = 0,
                is_cached = False
            )

            session.add(search_analytics)
            await session.flush()
            logger.info(f"Search Analytics ID: {search_analytics.id}")

            # Save to cache for next time
            # await SearchCache.set(query_text, search_output)

            search_output = {
                "sources": final_results,
                "query_time": round(query_time, 2),
                "domain": domain_name,
                "strategy": strategy_used,
                "num_candidates": len(candidates),
                "search_id": search_analytics.id
            }

            return search_output

    async def _resolve_domain(
        self, session, domain_name: Optional[str]
    ) -> tuple[Optional[UUID], float]:
        """Resolve domain name to ID and get threshold."""
        if not domain_name:
            return None
        
        result = await session.execute(
            select(Domain.id).where(Domain.name == domain_name)
        )
        domain_id = result.scalar_one_or_none()
        
        logger.info(f"Domain id found - {domain_id}")
        return domain_id

    async def _vector_search(
        self,
        session,
        query_embedding: np.ndarray,
        domain_id: Optional[UUID],
        domain_name: Optional[str],
        limit: int,
    ) -> List[RerankCandidate]:
        """Execute vector similarity search."""
        distance_func = DocumentChunk.embedding.cosine_distance(
            query_embedding.tolist()
        )

        stmt = select(
            DocumentChunk, (1 - distance_func).label("similarity")
        ).order_by(distance_func.asc())

        if domain_id:
            stmt = stmt.where(DocumentChunk.domain_id == domain_id)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        rows = result.all()

        return [
            RerankCandidate(
                chunk_id=str(chunk.id),
                document_id=str(chunk.document_id),
                domain=domain_name,
                text=chunk.text,
                vector_similarity=float(similarity),
                quality_score=chunk.quality_score,
                chunk_type=chunk.chunk_type,
                chunk_index=chunk.chunk_index,
                keywords=chunk.keywords,
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                file_url=None,
                embedding=(
                    np.array(chunk.embedding) if chunk.embedding is not None else None
                ),
            )
            for chunk, similarity in rows
        ]

    async def get_search_history(self, limit:int = 10, offset:int = 0, domain:str = "general") -> List[Dict]:
        """List of query search results"""
        async with db_manager.session() as session:

            stmt_subquery = (
                select(func.array_agg(DocumentChunk.text))
                .where(DocumentChunk.id == func.any(SearchAnalytics.result_chunk_ids))
                .scalar_subquery()
                .correlate(SearchAnalytics)
            )

            analytics_stmt = (
                select(SearchAnalytics, stmt_subquery.label("found_texts"))
                .order_by(SearchAnalytics.created_at.desc())
                .limit(limit)
            )

            result = await session.execute(analytics_stmt)
            search_results = result.all()

            return [
                {
                    "search_id": str(searches.id),
                    "query_text": searches.query_text,
                    "chunks": [
                        {"chunk_text":" ".join(t.split()), "similarity":round(s,4)}
                        for t,s in zip(chunk_texts or [], searches.similarity_scores or [])
                    ],
                    "embedding_time_ms": searches.embedding_time_ms,
                    "search_time_ms": searches.search_time_ms,
                    "total_processing_time": searches.total_processing_time,
                    "created_at": searches.created_at.isoformat()
                }
                for searches, chunk_texts in search_results
            ]
    
    async def get_search_history_by_id(self, search_id: UUID) -> SearchResult:
        """List of query search results"""
        
        logger.info("Searching in Redis Cache")
        cache_result = await SearchCache.get(str(search_id))

        if cache_result:
            logger.info("Cache hit, returning result from cache")
            return cache_result
        
        logger.info("Cache miss, performing db search")

        async with db_manager.session() as session:

            stmt_subquery = (
                select(func.array_agg(DocumentChunk.text))
                .where(DocumentChunk.id == func.any(SearchAnalytics.result_chunk_ids))
                .scalar_subquery()
                .correlate(SearchAnalytics)
            )

            analytics_stmt = (
                select(SearchAnalytics, stmt_subquery.label("found_texts"))
                .where(SearchAnalytics.id == search_id)
            )

            result = await session.execute(analytics_stmt)
            search_results = result.one_or_none()

            analytics, chunk_texts = search_results

            result = {
                    "search_id": str(analytics.id),
                    "query_text": analytics.query_text,
                    "chunks": [
                        {"chunk_text":" ".join(t.split()), "similarity":round(s,4)}
                        for t,s in zip(chunk_texts or [], analytics.similarity_scores or [])
                    ],
                    "embedding_time_ms": analytics.embedding_time_ms,
                    "search_time_ms": analytics.search_time_ms,
                    "total_processing_time": analytics.total_processing_time,
                    "created_at": analytics.created_at.isoformat()
                }

            logger.info("Storing accessed search_id results in redis cache")
            await SearchCache.set(str(analytics.id), result)
            
            return result