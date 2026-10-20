"""Chatbot agent implementation using LangGraph."""

import asyncio
import datetime as dt
import json
import time
import uuid
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
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
from app.agents.chatbot.context import build_model_context, render_turn_context, with_estimate_fallback
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

# Told to the model for the final call of a turn the server ended: no tools are
# bound, so it must answer in text from what it already has.
WRAP_UP_INSTRUCTION = (
    "Tools are no longer available this turn. Answer from the results above and say that the answer may be incomplete."
)
# Persisted as the answer if the wrap-up call itself fails.
STOPPED_FALLBACK_TEXT = (
    "I could not finish looking into this, so I have no complete answer. Try asking again, or narrow the question."
)

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


def repeated_call(messages: list[BaseMessage]) -> bool:
    """Whether the last AI message repeats a (tool, arguments) call already made this turn.

    "This turn" is everything after the last human message. A repeat means the
    model is going round in circles: the same lookup cannot return anything new.
    """
    turn: list[BaseMessage] = []
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        turn.append(message)
    ai_messages = [m for m in reversed(turn) if isinstance(m, AIMessage) and m.tool_calls]
    if len(ai_messages) < 2:
        return False

    def key(call: dict) -> tuple[str, str]:
        return call["name"], json.dumps(call["args"], sort_keys=True, default=str)

    earlier = {key(call) for message in ai_messages[:-1] for call in message.tool_calls}
    return any(key(call) in earlier for call in ai_messages[-1].tool_calls)


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

    async def _call_model(
        self, messages: list[BaseMessage], requested_model: str, *, with_tools: bool = True
    ) -> AIMessage:
        """One model call, timed under the name of the model that answered.

        A fallback can answer instead of the requested model; its name is on the
        response, and only known after the call, so the duration is observed
        rather than timed with a context manager.
        """
        started = time.perf_counter()
        response = await self.llm_service.call(messages, with_tools=with_tools)
        answering_model = response.response_metadata.get("model_name") or requested_model
        llm_inference_duration_seconds.labels(model=answering_model).observe(time.perf_counter() - started)
        logger.info(
            "llm_response_generated",
            model=answering_model,
            with_tools=with_tools,
            environment=settings.ENVIRONMENT.value,
        )
        return process_llm_response(response)

    async def _wrap_up(self, messages: list[BaseMessage], model_name: str, conversation_id: str) -> AIMessage:
        """The final answer of a turn the server ended: a tool-less model call, or the fixed text."""
        try:
            answer = await self._call_model(
                [*messages, SystemMessage(content=WRAP_UP_INSTRUCTION)], model_name, with_tools=False
            )
            if answer.text.strip() and not answer.tool_calls:
                return answer
        except Exception as e:
            logger.exception("llm_wrap_up_failed", conversation_id=conversation_id, error=str(e))
        return AIMessage(content=STOPPED_FALLBACK_TEXT)

    async def _model_context(self, state: GraphState, config: RunnableConfig, llm: BaseChatModel) -> list[BaseMessage]:
        """The messages for this turn's model calls; the wrap-up call builds on the same ones.

        The turn context is absent until a route sets it: the toolkit's preamble is then
        empty, and the model still gets today's date and the user's memory.
        """
        ctx = config.get("configurable", {}).get("turn_context")
        preamble = await self.toolkit.preamble(ctx) if ctx is not None else ""
        return build_model_context(
            state.messages,
            system_prompt=load_system_prompt(),
            turn_context_text=render_turn_context(
                today=dt.date.today(), memory=state.long_term_memory, preamble=preamble
            ),
            budget_tokens=settings.llm.CHAT_HISTORY_MAX_TOKENS,
            count_tokens=with_estimate_fallback(llm.get_num_tokens_from_messages),
        )

    async def _chat(self, state: GraphState, config: RunnableConfig) -> Command:
        """Process the chat state and generate a response.

        A response with tool calls goes on to the tools unless the turn has used
        its steps or the model repeats a call; then its calls are dropped and a
        tool-less wrap-up answer ends the turn, marked in `stopped`.
        """
        current_llm = self.llm_service.get_llm()
        model_name = self.llm_service.current_model_name()
        conversation_id = config["configurable"]["thread_id"]

        messages = await self._model_context(state, config, current_llm)

        try:
            response_message = await self._call_model(messages, model_name)
        except Exception as e:
            logger.exception(
                "llm_call_failed_all_models",
                conversation_id=conversation_id,
                error=str(e),
                environment=settings.ENVIRONMENT.value,
            )
            raise Exception(f"failed to get llm response after trying all models: {str(e)}")

        if not response_message.tool_calls:
            return Command(update={"messages": [response_message]}, goto=END)

        if state.turn_steps + 1 >= settings.llm.CHAT_MAX_STEPS:
            reason = "step_limit"
        elif repeated_call([*state.messages, response_message]):
            reason = "repeated_call"
        else:
            return Command(
                update={"messages": [response_message], "turn_steps": state.turn_steps + 1}, goto="tool_call"
            )

        logger.warning("chat_turn_stopped", conversation_id=conversation_id, reason=reason, steps=state.turn_steps)
        # The tool-calling response is not persisted: a stored AI message with calls
        # and no results would be a dangling call in every later turn's history.
        final = await self._wrap_up(messages, model_name, conversation_id)
        final.id = final.id or str(uuid.uuid4())
        return Command(update={"messages": [final], "stopped": {**state.stopped, final.id: reason}}, goto=END)

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
