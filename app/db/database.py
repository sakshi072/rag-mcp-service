"""
Database connection and session management for PostgreSQL with pgvector
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
import logging
from app.core.settings import settings
from app.core.exceptions import DatabaseConnectionException, DatabaseException


logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Modern Base class for SQLAlchemy 2.0 models"""
    pass


class DatabaseManager:
    """Manages database connections and sessions"""

    def __init__(self):
        """
        Initialize database manager

        Args:
            url: Database connection URL
        """
        self.url = settings.database.url
        self.engine: AsyncEngine = None
        self.session_factory: async_sessionmaker = None

    def initialize(self):
        """Initialize database engine and session factory"""
        if self.engine is not None:
            return

        # Create async engine
        self.engine = create_async_engine(
            self.url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )

        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for database sessions

        Usage:
            async with db_manager.session() as session:
                result = await session.execute(query)
        """
        if self.session_factory is None:
            self.initialize()

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except OperationalError as e:
                # Connection-level failures: can't reach/talk to the DB at all.
                await session.rollback()
                logger.error(f"Database connection failure: {e}", exc_info=True)
                raise DatabaseConnectionException(reason=str(e.orig) if e.orig else str(e)) from e
            except IntegrityError as e:
                # Constraint violations (unique/FK/check) - a client-caused
                # conflict, not a server failure, so this maps to 409.
                await session.rollback()
                logger.warning(f"Database integrity violation: {e}")
                raise DatabaseException(
                    message="A database constraint was violated",
                    error_code="INTEGRITY_VIOLATION",
                    status_code=409,
                    details={"reason": str(e.orig) if e.orig else str(e)},
                ) from e
            except SQLAlchemyError as e:
                # Catch-all for any other SQLAlchemy error type not handled
                # above (query errors, timeouts, etc).
                await session.rollback()
                logger.error(f"Unhandled database error: {e}", exc_info=True)
                raise DatabaseException(
                    message="A database error occurred",
                    details={"reason": str(e)},
                ) from e
            except Exception:
                # Anything else (including our own RetrievalBaseException
                # subclasses raised by business logic inside the block) -
                # roll back and propagate unchanged.
                await session.rollback()
                raise
            finally:
                await session.close()

    async def create_tables(self):
        """Create all tables (for development/testing)"""
        if self.engine is None:
            self.initialize()

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """Drop all tables (for development/testing)"""
        if self.engine is None:
            self.initialize()

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


# Global database manager instance
db_manager = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function for FastAPI endpoints

    Usage:
        @app.get("/documents")
        async def get_documents(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Document))
            return result.scalars().all()
    """
    async with db_manager.session() as session:
        yield session


async def startup_database():
    """Initialize database on application startup"""
    logger.info("Connecting to PostgreSQL...")
    db_manager.initialize()
    logger.info("Database connected!")


async def shutdown_database():
    """Close database connections on application shutdown"""
    logger.info("Closing database connections...")
    await db_manager.close()
    logger.info("Database connections closed!")
