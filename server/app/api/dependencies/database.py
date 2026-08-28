"""Database session dependencies for FastAPI endpoints."""

from typing import (
    Annotated,
    AsyncGenerator,
    Optional,
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


def _integrity_diagnostics(exc: IntegrityError) -> tuple[Optional[str], Optional[str]]:
    """Pull the constraint name and SQLSTATE out of an IntegrityError.

    Both drivers are handled because they expose the PostgreSQL error fields
    in different places, and only one of them is ever right at a time:

    - psycopg puts them on `orig.diag`.
    - asyncpg does not. SQLAlchemy's asyncpg dialect raises its *own* DBAPI
      error (AsyncAdapt_asyncpg_dbapi.IntegrityError, which carries nothing
      but pgcode/sqlstate) `from` the asyncpg exception, so the object that
      holds constraint_name is `orig.__cause__`.

    This app runs asyncpg (app/database/engine.py), so the second branch is
    the live one; the first is kept because a `.diag` lookup alone silently
    returns None on this stack, which is the failure that motivated the
    helper.

    Never widen this to `orig.detail` or `str(exc)`: those carry the
    offending values ("Key (email)=(...) already exists.", SQLAlchemy's
    "[parameters: ...]" suffix), which is the PII the caller is careful not
    to log.

    Args:
        exc: The SQLAlchemy IntegrityError.

    Returns:
        (constraint name, SQLSTATE), either of which may be None.
    """
    orig = exc.orig
    diag = getattr(orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None) if diag is not None else None
    if constraint is None:
        constraint = getattr(getattr(orig, "__cause__", None), "constraint_name", None)
    return constraint, getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


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
        # Log the constraint name and SQLSTATE — see _integrity_diagnostics
        # for where each driver hides them, and for why nothing wider than
        # those two fields may be logged here.
        # Deliberately logger.error(), not .exception(), diverging from this
        # repo's usual "use .exception() to preserve tracebacks" convention
        # (see server/CLAUDE.md): .exception() renders the traceback, whose
        # terminal line is str(e) — SQLAlchemy's "[parameters: ...]" suffix,
        # which for a unique-constraint violation on a PII column (e.g.
        # User.email) puts that value straight into the logs, and the
        # chained psycopg UniqueViolation frame adds a "DETAIL: Key
        # (email)=(...) already exists." line on top. The constraint name is
        # the actionable, non-PII datum here, and the auto-injected
        # correlation_id still ties this log record to its request, so
        # nothing is lost by not rendering the traceback. Only the log gets
        # the constraint name; it is intentionally not included in the
        # raised exception's context, since that context reaches API
        # clients via service_exception_handler.
        constraint, sqlstate = _integrity_diagnostics(e)
        logger.error(
            "database_integrity_error",
            constraint=constraint or "unknown",
            sqlstate=sqlstate,
        )
        raise DatabaseConflictError(
            "Database constraint violation",
        ) from e
    except OperationalError as e:
        await session.rollback()
        logger.exception("database_operational_error", error=str(e))
        raise DatabaseConnectionError(
            "Database connection or operational error",
        ) from e
    except DBAPIError as e:
        await session.rollback()
        logger.exception("database_api_error", error=str(e))
        raise DatabaseError(
            "Database API error",
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
