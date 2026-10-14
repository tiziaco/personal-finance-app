"""Memory factory and utilities for agent long-term memory management."""

import uuid
from typing import Any, Dict, Optional

from mem0 import AsyncMemory

from app.core.config import settings
from app.core.logging import logger

_memory_instance: Optional[AsyncMemory] = None

# Keys mem0 owns on the memory record itself. `add()` takes user_id as a named
# argument, and since 2.0 it warns and drops any of these found in `metadata`.
# The graph config we hand through carries user_id for Langfuse, so strip them.
MEM0_IDENTITY_KEYS = frozenset({"user_id", "agent_id", "run_id", "actor_id"})


def _openrouter_credentials() -> Dict[str, Any]:
    """The key and base URL every mem0 client uses.

    Passed explicitly rather than left to mem0's environment lookup. Its OpenAI
    LLM switches to OpenRouter only when OPENROUTER_API_KEY is in os.environ,
    and pydantic-settings does not put .env.<ENV> values there. Setting both
    base URLs makes either branch land on OpenRouter.
    """
    return {
        "api_key": settings.llm.OPENROUTER_API_KEY.get_secret_value(),
        "openai_base_url": settings.llm.LLM_BASE_URL,
    }


def _memory_llm_config() -> Dict[str, Any]:
    """Config for the model mem0 uses to extract and consolidate facts.

    mem0 2.0's `_is_reasoning_model` excludes gpt-5.x on the assumption it
    accepts `temperature`. The released gpt-5-nano and gpt-5-mini do not — they
    reject every value but the default, so extraction 400s and every memory
    write is lost. `is_reasoning_model` is 2.0's explicit override and takes
    precedence; set it only where mem0 gets it wrong, since its detection is
    already right for o1/o3 and the gpt-4 family.
    """
    config: Dict[str, Any] = {
        "model": settings.memory.MODEL,
        **_openrouter_credentials(),
        "openrouter_base_url": settings.llm.LLM_BASE_URL,
    }
    if settings.memory.MODEL.lower().rsplit("/", 1)[-1].startswith("gpt-5"):
        config["is_reasoning_model"] = True
    return config


async def create_memory() -> AsyncMemory:
    """Initialize and return the singleton AsyncMemory, backed by pgvector."""
    global _memory_instance

    if _memory_instance is None:
        # Checked before mem0 sees the config: given an empty key, its OpenAI
        # client falls back to OPENAI_API_KEY from the environment and would
        # send that secret to OpenRouter. Callers log this and carry on with no
        # long-term memory, as they do for any other memory failure.
        if not settings.llm.OPENROUTER_API_KEY.get_secret_value():
            raise RuntimeError("OPENROUTER_API_KEY is not set: long-term memory needs it")

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
                    "config": {"model": settings.memory.EMBEDDER_MODEL, **_openrouter_credentials()},
                },
                # To steer extraction, mem0 2.0 takes a single top-level
                # "custom_instructions"; the 1.x "custom_fact_extraction_prompt"
                # and "custom_update_memory_prompt" keys were removed and now
                # fail config validation.
            }
        )
    return _memory_instance


async def get_relevant_memory(user_id: uuid.UUID, query: str) -> str:
    """Relevant memories for a user, formatted; "" if none or on any error."""
    try:
        memory = await create_memory()
        # mem0 2.0 moved entity ids off the signature: a top-level `user_id=`
        # now raises ValueError. `top_k` and `threshold` are passed explicitly
        # rather than inherited from the library's defaults — see
        # MemorySettings for why they are ours to pin.
        results = await memory.search(
            query=query,
            filters={"user_id": str(user_id)},
            top_k=settings.memory.SEARCH_TOP_K,
            threshold=settings.memory.SEARCH_THRESHOLD,
        )

        if not results or "results" not in results or not results["results"]:
            return ""

        return "\n".join([f"* {result['memory']}" for result in results["results"]])
    except Exception as e:
        logger.exception("failed_to_get_relevant_memory", error=str(e), user_id=user_id, query=query)
        return ""


async def delete_user_memory(user_id: uuid.UUID) -> None:
    """Delete all long-term memory entries for a user (GDPR erasure)."""
    try:
        memory = await create_memory()
        await memory.delete_all(user_id=str(user_id))
        logger.info("user_memory_deleted", user_id=user_id)
    except Exception as e:
        logger.exception("failed_to_delete_user_memory", error=str(e), user_id=user_id)


async def update_memory(
    user_id: uuid.UUID,
    messages: list[dict],
    metadata: dict = None,
) -> None:
    """Update the long-term memory with new messages."""
    try:
        memory = await create_memory()
        clean_metadata = {k: v for k, v in (metadata or {}).items() if k not in MEM0_IDENTITY_KEYS}
        await memory.add(messages, user_id=str(user_id), metadata=clean_metadata)
        logger.info("long_term_memory_updated_successfully", user_id=user_id)
    except Exception as e:
        logger.exception(
            "failed_to_update_long_term_memory",
            user_id=user_id,
            error=str(e),
        )
