"""Chatbot agent implementation using LangGraph."""

import asyncio
import json
import time
import uuid
from typing import Optional

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.config import get_stream_writer
from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import RunnableConfig
from pydantic import BaseModel, ValidationError

from app.agents.base import BaseAgent
from app.agents.chatbot.events import ToolFinishedEvent, ToolStartedEvent
from app.agents.chatbot.prompts import load_system_prompt
from app.agents.chatbot.state import GraphState
from app.agents.chatbot.title import first_exchange, generate_title
from app.agents.chatbot.toolkit import (
    ToolArgumentError,
    ToolDisplay,
    Toolkit,
    ToolOutcome,
    TurnContext,
)
from app.agents.graph import (
    drop_unanswered_tool_calls,
    dump_messages,
    prepare_messages,
    process_llm_response,
)
from app.core.config import settings
from app.core.logging import logger
from app.core.metadata import PROJECT_NAME
from app.core.metrics import (
    llm_inference_duration_seconds,
    tool_call_duration_seconds,
    tool_calls_total,
)
from app.integrations.llm import LLMService

# What the model is told when a tool call does not produce a result. Fixed text
# rather than the exception: a tool result becomes a ToolMessage in graph state,
# which LangGraph persists to the checkpoint tables and which re-enters the
# model's context on every later turn of the conversation. Upstream error strings
# do not belong in either place.
TOOL_FAILED_MESSAGE = "The tool failed to run. Tell the user this information could not be retrieved right now."
TOOL_UNKNOWN_MESSAGE = "That tool does not exist. Answer without it."

# Tool arguments are logged, so they need a ceiling: they are the most useful
# field when diagnosing a bad answer, but a tool taking a large payload would
# otherwise dump it into every line.
TOOL_ARGS_LOG_LIMIT = 200


def _format_tool_args(args: dict) -> str:
    """Render tool arguments as JSON, truncated past `TOOL_ARGS_LOG_LIMIT`."""
    rendered = json.dumps(args, default=str, ensure_ascii=False)
    if len(rendered) <= TOOL_ARGS_LOG_LIMIT:
        return rendered
    return rendered[:TOOL_ARGS_LOG_LIMIT] + "..."


def _format_validation_error(error: ValidationError) -> str:
    """Render argument validation errors for the model: which argument, and what is wrong with it."""
    problems = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}" for e in error.errors())
    return f"Invalid arguments: {problems}"


class ChatbotAgent(BaseAgent):
    """A LangGraph conversational workflow with tools, memory and checkpointing."""

    def __init__(self, toolkit: Toolkit | None = None):
        super().__init__()

        self.toolkit = toolkit or Toolkit.empty()
        # Its own service, not the shared singleton: the chat's reply budget and
        # reasoning effort are set here and the tools bound are this agent's.
        self.llm_service = LLMService(
            max_tokens=settings.llm.CHAT_REPLY_MAX_TOKENS,
            reasoning_effort=settings.llm.CHAT_REASONING_EFFORT,
        )
        self.llm_service.bind_tools([tool.as_schema() for tool in self.toolkit.tools])
        self.tools_by_name = {tool.name: tool for tool in self.toolkit.tools}

        logger.info(
            "chatbot_agent_initialized",
            model=settings.llm.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    async def _chat(self, state: GraphState, config: RunnableConfig) -> Command:
        """Process the chat state and generate a response."""
        current_llm = self.llm_service.get_llm()
        model_name = self.llm_service.current_model_name()

        system_prompt = load_system_prompt(long_term_memory=state.long_term_memory)

        messages = prepare_messages(drop_unanswered_tool_calls(state.messages), current_llm, system_prompt)

        try:
            with llm_inference_duration_seconds.labels(model=model_name).time():
                response_message = await self.llm_service.call(dump_messages(messages))

            response_message = process_llm_response(response_message)

            logger.info(
                "llm_response_generated",
                conversation_id=config["configurable"]["thread_id"],
                model=model_name,
                environment=settings.ENVIRONMENT.value,
            )

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

    async def title_for(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
        """A title for a conversation from its first exchange, on the current model, or None.

        None before the first reply, or when the model fails or answers with
        nothing usable: a title is cosmetic, and the client asks again after the
        next completed reply.
        """
        exchange = first_exchange(await self.get_chat_history(conversation_id))
        if exchange is None:
            return None
        user_text, reply_text = exchange
        try:
            return await generate_title(
                user_text, reply_text, self.llm_service.current_model_name(), conversation_id, user_id
            )
        except Exception:
            logger.exception("conversation_title_generation_failed", conversation_id=conversation_id)
            return None

    async def _invoke_tool(
        self, tool_call: dict, ctx: TurnContext | None, config: RunnableConfig | None = None
    ) -> ToolMessage:
        """Run one tool call, recording what happened.

        This node hand-rolls the execution loop rather than using LangChain's
        prebuilt ToolNode, so error handling belongs here and not on the tools:
        one place covers a tool raising *and* a name the model invented, and
        every tool added later is covered without opting in. The returned
        ToolMessage carries `status="error"` if there was no result. Three
        failures, three messages: arguments that do not validate or a
        `ToolArgumentError` return text written for the model; anything else is
        a crash and returns the fixed `TOOL_FAILED_MESSAGE`.
        """
        tool_name = tool_call["name"]
        tool = self.tools_by_name.get(tool_name)

        def error_message(content: str) -> ToolMessage:
            return ToolMessage(content=content, name=tool_name, tool_call_id=tool_call["id"], status="error")

        if tool is None:
            # A hallucinated name used to raise KeyError out of the graph and
            # surface as a bare 500 with nothing naming the tool.
            logger.error(
                "tool_call_unknown_tool",
                tool_name=tool_name,
                known_tools=sorted(self.tools_by_name),
            )
            tool_calls_total.labels(tool=tool_name, outcome="unknown_tool").inc()
            return error_message(TOOL_UNKNOWN_MESSAGE)

        tool_args = _format_tool_args(tool_call["args"])
        logger.debug("tool_call_started", tool_name=tool_name, tool_args=tool_args)
        started = time.perf_counter()

        def finish(outcome: str) -> float:
            # Timed on every outcome: a tool that fails slowly is a different
            # problem from one that fails fast.
            duration = time.perf_counter() - started
            tool_call_duration_seconds.labels(tool=tool_name).observe(duration)
            tool_calls_total.labels(tool=tool_name, outcome=outcome).inc()
            return duration

        try:
            args = tool.args_schema.model_validate(tool_call["args"])
        except ValidationError as e:
            duration = finish("invalid_args")
            message = _format_validation_error(e)
            logger.warning(
                "tool_call_invalid_args",
                tool_name=tool_name,
                tool_args=tool_args,
                duration_ms=round(duration * 1000),
                error=message,
            )
            return error_message(message)

        try:
            if ctx is None:
                # Nothing sets a turn context until the route does; a tool call with
                # none is a wiring bug, handled like any other crash.
                raise RuntimeError("tool call without a turn context")

            async def run(model: BaseModel) -> ToolOutcome:
                return await tool.run(model, ctx)

            # A runnable so the graph's Langfuse callback records one span per call,
            # named for the tool, with its arguments and result.
            outcome = await RunnableLambda(run).ainvoke(args, config={**(config or {}), "run_name": tool_name})
        except ToolArgumentError as e:
            duration = finish("invalid_args")
            logger.warning(
                "tool_call_rejected_args",
                tool_name=tool_name,
                tool_args=tool_args,
                duration_ms=round(duration * 1000),
                error=str(e),
            )
            return error_message(str(e))
        except Exception as e:
            duration = finish("error")
            logger.exception(
                "tool_call_failed",
                tool_name=tool_name,
                tool_args=tool_args,
                duration_ms=round(duration * 1000),
                error=str(e),
            )
            return error_message(TOOL_FAILED_MESSAGE)

        duration = finish("success")
        logger.info(
            "tool_call_completed",
            tool_name=tool_name,
            tool_args=tool_args,
            duration_ms=round(duration * 1000),
            result_chars=len(outcome.content),
        )
        return ToolMessage(
            content=outcome.content,
            name=tool_name,
            tool_call_id=tool_call["id"],
            artifact=outcome.display.model_dump(),
        )

    async def _tool_call(self, state: GraphState, config: RunnableConfig) -> Command:
        """Run every tool call on the last message concurrently, then route back to chat.

        Results keep the order of the calls. Each call announces itself and its end
        on the custom stream so the client can show it running.
        """
        ctx = config.get("configurable", {}).get("turn_context")
        writer = get_stream_writer()

        async def one(tool_call: dict) -> ToolMessage:
            tool = self.tools_by_name.get(tool_call["name"])
            if tool is not None:
                writer(ToolStartedEvent(id=tool_call["id"], name=tool.name, title=tool.title))
            message = await self._invoke_tool(tool_call, ctx, config)
            if tool is not None:
                ok = message.status == "success"
                display = ToolDisplay.model_validate(message.artifact) if ok else None
                writer(ToolFinishedEvent(id=tool_call["id"], ok=ok, display=display))
            return message

        outputs = await asyncio.gather(*(one(tool_call) for tool_call in state.messages[-1].tool_calls))
        return Command(update={"messages": list(outputs)}, goto="chat")

    async def create_graph(self, checkpointer: AsyncPostgresSaver) -> CompiledStateGraph:
        """Create and compile the chatbot LangGraph workflow."""
        try:
            graph_builder = StateGraph(GraphState)
            graph_builder.add_node("chat", self._chat, ends=["tool_call", END])
            graph_builder.add_node("tool_call", self._tool_call, ends=["chat"])
            graph_builder.set_entry_point("chat")
            graph_builder.set_finish_point("chat")

            self._graph = graph_builder.compile(
                checkpointer=checkpointer,
                name=f"{PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})",
            )

            logger.info(
                "graph_created",
                graph_name=f"{PROJECT_NAME} Agent",
                environment=settings.ENVIRONMENT.value,
                has_checkpointer=checkpointer is not None,
            )
        except Exception as e:
            logger.exception("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
            raise

        return self._graph
