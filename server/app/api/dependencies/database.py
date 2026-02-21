"""Database session dependencies for FastAPI endpoints."""

from typing import (
    Annotated,
    AsyncGenerator,
)

from fastapi import (
    Depends,
    Request,
)
from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
    OperationalError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.database.context import (
    clear_session_context,
    set_session_context,
)
from app.exceptions.base import (
    DatabaseConflictError,
    DatabaseConnectionError,
    DatabaseError,
)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Core dependency for database sessions.
    
    Args:
        request: FastAPI request object
        
    Yields:
        AsyncSession: Database session
        
    Raises:
        RuntimeError: If session factory not initialized
    """
    if not hasattr(request.app.state, "session_factory"):
        logger.error("session_factory_not_initialized")
        raise RuntimeError("Database session factory not initialized")
    
    session = request.app.state.session_factory()
    try:
        # Set RLS context if user is authenticated
        if hasattr(request.state, "user_id"):
            await set_session_context(session, request.state.user_id)
        
        yield session
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        logger.exception("database_integrity_error", error=str(e))
        # Extract constraint name if available for better error messages
        constraint = getattr(e.orig, "constraint_name", None) if hasattr(e, "orig") else None
        raise DatabaseConflictError(
            "Database constraint violation",
            constraint=constraint,
            detail=str(e.orig) if hasattr(e, "orig") else str(e)
        ) from e
    except OperationalError as e:
        await session.rollback()
        logger.exception("database_operational_error", error=str(e))
        raise DatabaseConnectionError(
            "Database connection or operational error",
            detail=str(e.orig) if hasattr(e, "orig") else str(e)
        ) from e
    except DBAPIError as e:
        await session.rollback()
        logger.exception("database_api_error", error=str(e))
        raise DatabaseError(
            "Database API error",
            detail=str(e.orig) if hasattr(e, "orig") else str(e)
        ) from e
    except Exception as e:
        await session.rollback()
        logger.exception("database_session_error", error=str(e))
        raise
    finally:
        # Clear RLS context to prevent leaking to pooled connections
        await clear_session_context(session)
        await session.close()


# Type alias for cleaner endpoint signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
