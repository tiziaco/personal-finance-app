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
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
    OperationalError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.core.logging import logger
from app.exceptions.base import (
    DatabaseConflictError,
    DatabaseConnectionError,
    DatabaseError,
    ServiceError,
)


def _integrity_diagnostics(exc: IntegrityError) -> tuple[Optional[str], Optional[str]]:
    """Pull the constraint name and SQLSTATE out of an IntegrityError.

    The drivers hide them in different places, and only one branch is ever
    right: psycopg puts them on `orig.diag`; asyncpg does not, because
    SQLAlchemy's dialect raises its own DBAPI error carrying only pgcode
    `from` the asyncpg one, so constraint_name lives on `orig.__cause__`. This
    app runs asyncpg, so the second branch is the live one — a `.diag` lookup
    alone silently returns None here, which is what motivated the helper.

    Never widen to `orig.detail` or `str(exc)`: both carry the offending values
    ("Key (email)=(...) already exists.", SQLAlchemy's "[parameters: ...]"
    suffix), which is the PII the caller is careful not to log.
    """
    orig = exc.orig
    diag = getattr(orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None) if diag is not None else None
    if constraint is None:
        constraint = getattr(getattr(orig, "__cause__", None), "constraint_name", None)
    return constraint, getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """One session and one transaction per request, committed before the response is sent.

    `DbSession` binds this with `scope="function"`, and that keyword is the
    transaction boundary: the post-`yield` block runs after the path
    operation returns and before the response goes on the wire. With the
    default `"request"` scope the commit ran after the bytes were sent, so a
    200 could precede a failed commit. `tests/unit/database/test_dependencies.py`
    pins the keyword and the order.

    Consequences routes rely on:
    - A commit-time failure reaches the exception handlers (a unique violation is a 409).
    - Deferred event handlers run after the commit and before the response, so they add
      to its latency.
    - The session is closed by the time a `BackgroundTasks` callable or a `StreamingResponse`
      body runs. Neither may use it; `expire_on_commit=False` is what lets them read
      attributes already loaded.
    """
    if not hasattr(request.app.state, "session_factory"):
        logger.error("session_factory_not_initialized")
        raise RuntimeError("Database session factory not initialized")

    session = request.app.state.session_factory()
    events.begin()
    try:
        yield session
        await session.commit()
        # Deferred handlers run only once the request's writes are durable; a
        # request that raised above never reaches this line, and its queue is
        # discarded with the request context (architecture §8).
        await events.flush(request.app.state.session_factory)
    except IntegrityError as e:
        await session.rollback()
        # logger.error(), not .exception(), against this repo's usual
        # traceback-preserving convention (server/CLAUDE.md): the traceback ends
        # in str(e) — SQLAlchemy's "[parameters: ...]" suffix — which on a
        # unique violation over a PII column puts that value in the logs. The
        # constraint name is the actionable non-PII datum, and correlation_id
        # still ties the record to its request. It stays out of the raised
        # exception's context, which reaches API clients.
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
    except (ServiceError, RequestValidationError):
        # Raised by the route or a dependency and answered by its own handler, which logs it.
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("database_session_error", error=str(e))
        raise
    finally:
        await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db_session, scope="function")]


async def release_connection(session: AsyncSession) -> None:
    """Commit the request's work so far, handing its pool connection back before a model call.

    A model call takes seconds, and the request's session would otherwise hold its
    connection idle in a transaction through it; under concurrent requests that starves
    the pool. Call it only where nothing committed so far depends on what follows. The
    session opens a new transaction on its next use, which `get_db_session` commits after
    the route as usual. It is the one commit outside `get_db_session`, and only a request
    that awaits a model call uses it.
    """
    await session.commit()
