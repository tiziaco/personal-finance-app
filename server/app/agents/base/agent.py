"""Base agent class for all LangGraph agents."""

import asyncio
from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    AsyncGenerator,
    Optional,
)

from langchain_core.messages import (
    BaseMessage,
    convert_to_openai_messages,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot
from mem0 import AsyncMemory

from app.agents.shared.checkpointing import create_connection_pool
from app.agents.shared.memory import (
    get_relevant_memory,
    update_memory,
)
from app.agents.shared.observability import create_graph_config
from app.core.config import settings
from app.core.logging import logger
from app.schemas import Message
from app.utils import dump_messages


class BaseAgent(ABC):
    """Abstract base class for all LangGraph agents.
    
    Provides common functionality for response handling, streaming, chat history,
    and memory management. Agents must implement create_graph() to define their
    specific workflow.
    
    The graph is pre-compiled at application startup and stored in _graph.
    Methods assume the graph is ready and will raise errors if called before initialization.
    """

    def __init__(self):
        """Initialize the base agent."""
        self._graph: Optional[CompiledStateGraph] = None
        self.memory: Optional[AsyncMemory] = None

    @abstractmethod
    async def create_graph(self, checkpointer: AsyncPostgresSaver) -> CompiledStateGraph:
        """Create and configure the LangGraph workflow.
        
        Must be implemented by each agent to define its specific workflow.
        This method is called once at application startup to pre-compile the graph.
        
        Args:
            checkpointer: The AsyncPostgresSaver instance for graph checkpointing.
        
        Returns:
            CompiledStateGraph: The configured and compiled LangGraph instance.
            
        Raises:
            Exception: If graph creation or compilation fails.
        """
        pass

    def is_ready(self) -> bool:
        """Check if the agent's graph has been compiled and is ready for use.
        
        Returns:
            bool: True if graph is compiled, False otherwise.
        """
        return self._graph is not None

    async def get_response(
        self,
        messages: list[Message],
        conversation_id: str,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Get a response from the agent.

        Args:
            messages: The messages to send to the agent.
            conversation_id: The conversation ID for Langfuse tracking.
            user_id: Optional user ID for Langfuse tracking.

        Returns:
            List of message dictionaries with role and content.
            
        Raises:
            RuntimeError: If graph is not initialized (should never happen with startup init).
        """
        if not self.is_ready():
            raise RuntimeError(
                "Agent graph not initialized. This should not happen if startup completed successfully."
            )
            
        config = create_graph_config(conversation_id, user_id)
        
        relevant_memory = (
            await get_relevant_memory(user_id, messages[-1].content)
        ) or "No relevant memory found."
        
        try:
            response = await self._graph.ainvoke(
                input={"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                config=config,
            )
            # Run memory update in background without blocking the response
            asyncio.create_task(
                update_memory(
                    user_id, convert_to_openai_messages(response["messages"]), config["metadata"]
                )
            )
            return self._process_messages(response["messages"])
        except Exception as e:
            logger.exception("error_getting_response", error=str(e), conversation_id=conversation_id)
            raise

    async def get_stream_response(
        self,
        messages: list[Message],
        conversation_id: str,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Get a streaming response from the agent.

        Args:
            messages: The messages to send to the agent.
            conversation_id: The conversation ID for the conversation.
            user_id: Optional user ID for the conversation.

        Yields:
            Tokens of the agent response.
            
        Raises:
            RuntimeError: If graph is not initialized (should never happen with startup init).
        """
        if not self.is_ready():
            raise RuntimeError(
                "Agent graph not initialized. This should not happen if startup completed successfully."
            )
            
        config = create_graph_config(conversation_id, user_id)
        
        relevant_memory = (
            await get_relevant_memory(user_id, messages[-1].content)
        ) or "No relevant memory found."

        try:
            async for token, _ in self._graph.astream(
                {"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                config=config,
                stream_mode="messages",
            ):
                try:
                    yield token.content
                except Exception as token_error:
                    logger.exception("error_processing_token", error=str(token_error), conversation_id=conversation_id)
                    # Continue with next token even if current one fails
                    continue

            # After streaming completes, get final state and update memory in background
            state: StateSnapshot = await self._graph.aget_state(config=config)
            if state.values and "messages" in state.values:
                asyncio.create_task(
                    update_memory(
                        user_id, convert_to_openai_messages(state.values["messages"]), config["metadata"]
                    )
                )
        except Exception as stream_error:
            logger.exception("error_in_stream_processing", error=str(stream_error), conversation_id=conversation_id)
            raise stream_error

    async def get_chat_history(self, conversation_id: str) -> list[Message]:
        """Get the chat history for a given conversation.

        Args:
            conversation_id: The conversation ID for the conversation.

        Returns:
            List of messages in the conversation history.
            
        Raises:
            RuntimeError: If graph is not initialized (should never happen with startup init).
        """
        if not self.is_ready():
            raise RuntimeError(
                "Agent graph not initialized. This should not happen if startup completed successfully."
            )

        state: StateSnapshot = await self._graph.aget_state(
            config={"configurable": {"thread_id": conversation_id}}
        )
        return self._process_messages(state.values["messages"]) if state.values else []

    async def clear_chat_history(self, conversation_id: str) -> None:
        """Clear all chat history for a given conversation.

        Args:
            conversation_id: The ID of the conversation to clear history for.

        Raises:
            Exception: If there's an error clearing the chat history.
        """
        # Get the connection pool (singleton - already initialized at startup)
        conn_pool = await create_connection_pool()

        # Use a connection for this specific operation
        async with conn_pool.connection() as conn:
            for table in settings.database.CHECKPOINT_TABLES:
                await conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (conversation_id,))
                logger.info("cleared_table_for_conversation", table=table, conversation_id=conversation_id)

    def _process_messages(self, messages: list[BaseMessage]) -> list[Message]:
        """Process LangChain messages into simple message dictionaries.
        
        Args:
            messages: List of LangChain BaseMessage objects.
            
        Returns:
            List of Message objects with role and content.
        """
        openai_style_messages = convert_to_openai_messages(messages)
        # Keep just assistant and user messages
        return [
            Message(role=message["role"], content=str(message["content"]))
            for message in openai_style_messages
            if message["role"] in ["assistant", "user"] and message["content"]
        ]

    def _get_last_response(self, messages: list[BaseMessage]) -> Message:
        """Extract the last assistant message from the response.
        
        Args:
            messages: List of LangChain BaseMessage objects.
            
        Returns:
            The last assistant Message.
        """
        openai_style_messages = convert_to_openai_messages(messages)
        # Find the last assistant message
        for message in reversed(openai_style_messages):
            if message["role"] == "assistant" and message["content"]:
                return Message(role="assistant", content=str(message["content"]))
        # Fallback: return empty assistant message if none found
        return Message(role="assistant", content="")
