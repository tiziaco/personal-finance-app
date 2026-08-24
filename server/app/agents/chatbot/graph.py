"""Chatbot agent implementation using LangGraph."""

from typing import Optional

from langchain_core.messages import ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import RunnableConfig

from app.agents.base import BaseAgent
from app.agents.chatbot.prompts import load_system_prompt
from app.agents.chatbot.state import GraphState
from app.agents.chatbot.tools import tools
from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import llm_inference_duration_seconds
from app.services.llm import llm_service
from app.utils import (
    dump_messages,
    prepare_messages,
    process_llm_response,
)


class ChatbotAgent(BaseAgent):
    """Chatbot agent that handles conversational interactions.
    
    This agent uses LangGraph to manage a conversational workflow with
    tool calling capabilities, long-term memory, and checkpointing.
    """

    def __init__(self):
        """Initialize the chatbot agent with LLM service and tools."""
        super().__init__()
        
        # Use the LLM service with tools bound
        self.llm_service = llm_service
        self.llm_service.bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        
        logger.info(
            "chatbot_agent_initialized",
            model=settings.llm.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    async def _chat(self, state: GraphState, config: RunnableConfig) -> Command:
        """Process the chat state and generate a response.

        Args:
            state: The current state of the conversation.
            config: Runtime configuration including thread_id and callbacks.

        Returns:
            Command object with updated state and next node to execute.
        """
        # Get the current LLM instance for metrics
        current_llm = self.llm_service.get_llm()
        model_name = (
            current_llm.model_name
            if current_llm and hasattr(current_llm, "model_name")
            else settings.llm.DEFAULT_LLM_MODEL
        )

        system_prompt = load_system_prompt(long_term_memory=state.long_term_memory)

        # Prepare messages with system prompt
        messages = prepare_messages(state.messages, current_llm, system_prompt)

        try:
            # Use LLM service with automatic retries and circular fallback
            with llm_inference_duration_seconds.labels(model=model_name).time():
                response_message = await self.llm_service.call(dump_messages(messages))

            # Process response to handle structured content blocks
            response_message = process_llm_response(response_message)

            logger.info(
                "llm_response_generated",
                conversation_id=config["configurable"]["thread_id"],
                model=model_name,
                environment=settings.ENVIRONMENT.value,
            )

            # Determine next node based on whether there are tool calls
            if response_message.tool_calls:
                goto = "tool_call"
            else:
                goto = END

            return Command(update={"messages": [response_message]}, goto=goto)
        except Exception as e:
            logger.exception(
                "llm_call_failed_all_models",
                conversation_id=config["configurable"]["thread_id"],
                error=str(e),
                environment=settings.ENVIRONMENT.value,
            )
            raise Exception(f"failed to get llm response after trying all models: {str(e)}")

    async def _tool_call(self, state: GraphState) -> Command:
        """Process tool calls from the last message.

        Args:
            state: The current agent state containing messages and tool calls.

        Returns:
            Command object with updated messages and routing back to chat.
        """
        outputs = []
        for tool_call in state.messages[-1].tool_calls:
            tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
            outputs.append(
                ToolMessage(
                    content=tool_result,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        return Command(update={"messages": outputs}, goto="chat")

    async def create_graph(self, checkpointer: AsyncPostgresSaver) -> CompiledStateGraph:
        """Create and configure the chatbot LangGraph workflow.
        
        Args:
            checkpointer: The AsyncPostgresSaver instance for graph checkpointing.

        Returns:
            CompiledStateGraph: The configured and compiled LangGraph instance.
            
        Raises:
            Exception: If graph creation or compilation fails.
        """
        try:
            graph_builder = StateGraph(GraphState)
            graph_builder.add_node("chat", self._chat, ends=["tool_call", END])
            graph_builder.add_node("tool_call", self._tool_call, ends=["chat"])
            graph_builder.set_entry_point("chat")
            graph_builder.set_finish_point("chat")

            self._graph = graph_builder.compile(
                checkpointer=checkpointer,
                name=f"{settings.PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})",
            )

            logger.info(
                "graph_created",
                graph_name=f"{settings.PROJECT_NAME} Agent",
                environment=settings.ENVIRONMENT.value,
                has_checkpointer=checkpointer is not None,
            )
        except Exception as e:
            logger.exception("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
            raise

        return self._graph
