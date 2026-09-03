"""Memory factory and utilities for agent long-term memory management."""

from typing import Any, Dict, Optional

from mem0 import AsyncMemory

from app.core.config import settings
from app.core.logging import logger

_memory_instance: Optional[AsyncMemory] = None

# Retrieval breadth for `get_relevant_memory`. Every hit is rendered into the
# agent's prompt, so these bound prompt size as much as they bound recall.
MEMORY_SEARCH_TOP_K = 20
MEMORY_SEARCH_THRESHOLD = 0.1

# Keys mem0 owns on the memory record itself. `add()` takes user_id as a named
# argument, and since 2.0 it warns and drops any of these found in `metadata`.
# The graph config we hand through carries user_id for Langfuse, so strip them.
MEM0_IDENTITY_KEYS = frozenset({"user_id", "agent_id", "run_id", "actor_id"})


def _memory_llm_config() -> Dict[str, Any]:
    """Config for the model mem0 uses to extract and consolidate facts.

    mem0 2.0 narrowed its reasoning-model detection. 1.x matched "gpt-5" as a
    substring; 2.0 matches an exact set plus the `o1-`/`o3-` prefixes, and
    deliberately excludes gpt-5.x variants on the assumption they accept
    `temperature` (see `_is_reasoning_model` in mem0/llms/base.py). The
    released gpt-5-nano and gpt-5-mini do not — they reject every temperature
    but the default, so extraction 400s and every memory write is lost.

    `is_reasoning_model` is the explicit override 2.0 added for this, and it
    takes precedence over the heuristic. Set it only where mem0 gets it wrong;
    for o1/o3 and the gpt-4 family its own detection is already right.
    """
    config: Dict[str, Any] = {"model": settings.memory.MODEL}
    if settings.memory.MODEL.lower().rsplit("/", 1)[-1].startswith("gpt-5"):
        config["is_reasoning_model"] = True
    return config


async def create_memory() -> AsyncMemory:
    """Initialize and return a singleton AsyncMemory instance.
    
    Returns:
        AsyncMemory: Configured memory instance with pgvector backend.
    """
    global _memory_instance
    
    if _memory_instance is None:
        # Not awaited: mem0ai 1.0.10 turned `AsyncMemory.from_config` from a
        # coroutine into a plain classmethod. Every other AsyncMemory method
        # used here (add/search/delete_all) is still async. Awaiting this one
        # raises TypeError, which the callers below swallow into a log line —
        # so the agent silently runs with no long-term memory at all.
        _memory_instance = AsyncMemory.from_config(
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
                    "config": _memory_llm_config(),
                },
                "embedder": {
                    "provider": "openai",
                    "config": {"model": settings.memory.EMBEDDER_MODEL},
                },
                # To steer extraction, mem0 2.0 takes a single top-level
                # "custom_instructions"; the 1.x "custom_fact_extraction_prompt"
                # and "custom_update_memory_prompt" keys were removed and now
                # fail config validation.
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
        # mem0 2.0 moved entity ids off the signature: a top-level `user_id=`
        # now raises ValueError. `top_k` and `threshold` are passed explicitly
        # rather than inherited — 2.0 already changed both defaults under us
        # (limit 100 -> top_k 20, threshold None -> 0.1) and every one of these
        # memories is pasted into the agent's prompt, so the breadth of the
        # retrieval belongs in this file rather than in the library's defaults.
        results = await memory.search(
            query=query,
            filters={"user_id": str(user_id)},
            top_k=MEMORY_SEARCH_TOP_K,
            threshold=MEMORY_SEARCH_THRESHOLD,
        )
        
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
        clean_metadata = {
            k: v for k, v in (metadata or {}).items() if k not in MEM0_IDENTITY_KEYS
        }
        await memory.add(messages, user_id=str(user_id), metadata=clean_metadata)
        logger.info("long_term_memory_updated_successfully", user_id=user_id)
    except Exception as e:
        logger.exception(
            "failed_to_update_long_term_memory",
            user_id=user_id,
            error=str(e),
        )
