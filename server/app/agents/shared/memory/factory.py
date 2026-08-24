"""Memory factory and utilities for agent long-term memory management."""

from typing import Optional

from mem0 import AsyncMemory

from app.core.config import settings
from app.core.logging import logger

_memory_instance: Optional[AsyncMemory] = None


async def create_memory() -> AsyncMemory:
    """Initialize and return a singleton AsyncMemory instance.
    
    Returns:
        AsyncMemory: Configured memory instance with pgvector backend.
    """
    global _memory_instance
    
    if _memory_instance is None:
        _memory_instance = await AsyncMemory.from_config(
            config_dict={
                "vector_store": {
                    "provider": "pgvector",
                    "config": {
                        "collection_name": settings.memory.COLLECTION_NAME,
                        "dbname": settings.database.DB,
                        "user": settings.database.USER,
                        "password": settings.database.PASSWORD.get_secret_value(),
                        "host": settings.database.HOST,
                        "port": settings.database.PORT,
                    },
                },
                "llm": {
                    "provider": "openai",
                    "config": {"model": settings.memory.MODEL},
                },
                "embedder": {
                    "provider": "openai",
                    "config": {"model": settings.memory.EMBEDDER_MODEL},
                },
                # "custom_fact_extraction_prompt": load_custom_fact_extraction_prompt(),
            }
        )
    return _memory_instance


async def get_relevant_memory(user_id: str, query: str) -> str:
    """Retrieve relevant memories for a user based on a query.
    
    Args:
        user_id: The user ID to search memories for.
        query: The query to search for relevant memories.
        
    Returns:
        Formatted string of relevant memories, or empty string if none found or error occurs.
    """
    try:
        memory = await create_memory()
        results = await memory.search(user_id=str(user_id), query=query)
        
        if not results or "results" not in results or not results["results"]:
            return ""
            
        return "\n".join([f"* {result['memory']}" for result in results["results"]])
    except Exception as e:
        logger.exception("failed_to_get_relevant_memory", error=str(e), user_id=user_id, query=query)
        return ""


async def delete_user_memory(user_id: str) -> None:
    """Delete all long-term memory entries for a user (GDPR erasure).

    Args:
        user_id: The user ID whose memories should be deleted.
    """
    try:
        memory = await create_memory()
        await memory.delete_all(user_id=str(user_id))
        logger.info("user_memory_deleted", user_id=user_id)
    except Exception as e:
        logger.exception("failed_to_delete_user_memory", error=str(e), user_id=user_id)


async def update_memory(
    user_id: str,
    messages: list[dict],
    metadata: dict = None,
) -> None:
    """Update the long-term memory with new messages.
    
    Args:
        user_id: The user ID to associate memories with.
        messages: The messages to store in long-term memory.
        metadata: Optional metadata to include with the memories.
    """
    try:
        memory = await create_memory()
        await memory.add(messages, user_id=str(user_id), metadata=metadata)
        logger.info("long_term_memory_updated_successfully", user_id=user_id)
    except Exception as e:
        logger.exception(
            "failed_to_update_long_term_memory",
            user_id=user_id,
            error=str(e),
        )
