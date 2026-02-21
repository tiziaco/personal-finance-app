"""Session context management for authentication and RLS."""

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger


async def set_session_context(session: AsyncSession, user_id: str) -> None:
    """Set the request context for the database session.
    
    Args:
        session: The async database session
        user_id: The authenticated user's ID (UUID string)
    """
    session.info["user_id"] = user_id
    
    await session.execute(text(f"SET app.current_user_id = '{user_id}'"))
    
    logger.debug("session_context_set", user_id=user_id)


def get_session_context(session: AsyncSession) -> Optional[dict]:
    """Get the request context from the session.
    
    Args:
        session: The async database session
        
    Returns:
        Optional[dict]: Context dictionary with user_id
    """
    return {
        "user_id": session.info.get("user_id")
    }


async def clear_session_context(session: AsyncSession) -> None:
    """Clear the request context from the session.
    
    Args:
        session: The async database session
    """
    session.info.pop("user_id", None)
    
    await session.execute(text("RESET app.current_user_id"))
    
    logger.debug("session_context_cleared")
