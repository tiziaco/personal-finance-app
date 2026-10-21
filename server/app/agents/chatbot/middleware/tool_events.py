"""Tool-call events, metrics and error texts around every tool execution.

Wraps the tools node's call to each tool. It announces the call and its end on the
custom stream, counts and times it, validates the arguments, and decides what the
model is told when there is no result: three failures, three messages. Arguments
that do not validate or a `ToolException` return text written for the model;
anything else is a crash and returns the fixed `TOOL_FAILED_MESSAGE`; a name the
model invented returns `TOOL_UNKNOWN_MESSAGE`. The library's tool node hands a
tool's exception to this hook unchanged (its default error handling re-raises
everything but its own argument-validation error), so the texts below are the
ones the model sees.
"""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException
from langgraph.types import Command
from pydantic import ValidationError

from app.core.logging import logger
from app.core.metrics import tool_call_duration_seconds, tool_calls_total

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


@dataclass(frozen=True)
class ToolCallStarted:
    """Written to the custom stream when a known tool starts running."""

    id: str
    name: str


@dataclass(frozen=True)
class ToolCallFinished:
    """Written to the custom stream when a known tool's call ends; `artifact` is its result's display data."""

    id: str
    ok: bool
    artifact: dict | None


def format_tool_args(args: dict) -> str:
    """Render tool arguments as JSON, truncated past `TOOL_ARGS_LOG_LIMIT`."""
    rendered = json.dumps(args, default=str, ensure_ascii=False)
    if len(rendered) <= TOOL_ARGS_LOG_LIMIT:
        return rendered
    return rendered[:TOOL_ARGS_LOG_LIMIT] + "..."


def format_validation_error(error: ValidationError) -> str:
    """Render argument validation errors for the model: which argument, and what is wrong with it."""
    problems = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}" for e in error.errors())
    return f"Invalid arguments: {problems}"


class ToolEventsMiddleware(AgentMiddleware):
    """Events on the custom stream, metrics, argument validation and the model-facing error texts."""

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Run one tool call, recording what happened. A failed call returns a `status="error"` message."""
        call = request.tool_call
        tool_name = call["name"]
        writer = request.runtime.stream_writer

        def error(content: str) -> ToolMessage:
            return ToolMessage(content=content, name=tool_name, tool_call_id=call["id"], status="error")

        if request.tool is None:
            # A hallucinated name used to raise KeyError out of the graph and
            # surface as a bare 500 with nothing naming the tool.
            logger.error("tool_call_unknown_tool", tool_name=tool_name)
            tool_calls_total.labels(tool=tool_name, outcome="unknown_tool").inc()
            return error(TOOL_UNKNOWN_MESSAGE)

        writer(ToolCallStarted(id=call["id"], name=tool_name))
        tool_args = format_tool_args(call["args"])
        logger.debug("tool_call_started", tool_name=tool_name, tool_args=tool_args)
        started = time.perf_counter()

        def finish(outcome: str) -> float:
            # Timed on every outcome: a tool that fails slowly is a different
            # problem from one that fails fast.
            duration = time.perf_counter() - started
            tool_call_duration_seconds.labels(tool=tool_name).observe(duration)
            tool_calls_total.labels(tool=tool_name, outcome=outcome).inc()
            return duration

        message: ToolMessage | Command
        try:
            request.tool.args_schema.model_validate(call["args"])
        except ValidationError as e:
            duration = finish("invalid_args")
            text = format_validation_error(e)
            logger.warning(
                "tool_call_invalid_args",
                tool_name=tool_name,
                tool_args=tool_args,
                duration_ms=round(duration * 1000),
                error=text,
            )
            message = error(text)
        else:
            try:
                message = await handler(request)
            except ToolException as e:
                duration = finish("invalid_args")
                logger.warning(
                    "tool_call_rejected_args",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    duration_ms=round(duration * 1000),
                    error=str(e),
                )
                message = error(str(e))
            except Exception as e:
                duration = finish("error")
                logger.exception(
                    "tool_call_failed",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    duration_ms=round(duration * 1000),
                    error=str(e),
                )
                message = error(TOOL_FAILED_MESSAGE)
            else:
                if isinstance(message, ToolMessage) and message.status == "error":
                    # The tool node turned an exception into a message (a pydantic ValidationError raised
                    # inside the tool body, say) with the library's text: a crash, not something to show the model.
                    duration = finish("error")
                    logger.error(
                        "tool_call_failed",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        duration_ms=round(duration * 1000),
                        error=str(message.content),
                    )
                    message = error(TOOL_FAILED_MESSAGE)
                else:
                    duration = finish("success")
                    logger.info(
                        "tool_call_completed",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        duration_ms=round(duration * 1000),
                        result_chars=len(message.content) if isinstance(message, ToolMessage) else None,
                    )

        ok = not (isinstance(message, ToolMessage) and message.status == "error")
        artifact = message.artifact if ok and isinstance(message, ToolMessage) else None
        writer(ToolCallFinished(id=call["id"], ok=ok, artifact=artifact))
        return message
