"""Bounds a turn: a step cap, repeated-call detection and the tool-less wrap-up call.

Outermost of the model-call hooks. A response with tool calls goes on to the tools
unless the turn has used its steps or the model repeats a call; then that response
is dropped (never returned, so never persisted or run) and a second, tool-less
call answers from what the turn already has. The final message is marked in
`stopped`, keyed by its id. A reply with neither text nor tool calls fails the turn.
"""

import json
import uuid
from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ExtendedModelResponse, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_config
from langgraph.types import Command

from app.agents.chatbot.context import TurnContext
from app.agents.chatbot.state import ChatState
from app.core.config import settings
from app.core.logging import logger

# Told to the model for the final call of a turn the server ended: no tools are
# bound, so it must answer in text from what it already has.
WRAP_UP_INSTRUCTION = (
    "Tools are no longer available this turn. Answer from the results above and say that the answer may be incomplete."
)
# Persisted as the answer if the wrap-up call itself fails.
STOPPED_FALLBACK_TEXT = (
    "I could not finish looking into this, so I have no complete answer. Try asking again, or narrow the question."
)


def _current_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    """The messages after the last human message, in order."""
    turn: list[BaseMessage] = []
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break
        turn.append(message)
    return turn[::-1]


def turn_steps(messages: list[BaseMessage]) -> int:
    """Model calls with tool calls so far this turn (AI messages with calls after the last human message)."""
    return sum(1 for m in _current_turn(messages) if isinstance(m, AIMessage) and m.tool_calls)


def repeated_call(messages: list[BaseMessage]) -> bool:
    """Whether the last AI message repeats a (tool, arguments) call already made this turn.

    "This turn" is everything after the last human message. A repeat means the
    model is going round in circles: the same lookup cannot return anything new.
    """
    ai_messages = [m for m in _current_turn(messages) if isinstance(m, AIMessage) and m.tool_calls]
    if len(ai_messages) < 2:
        return False

    def key(call: dict) -> tuple[str, str]:
        return call["name"], json.dumps(call["args"], sort_keys=True, default=str)

    earlier = {key(call) for message in ai_messages[:-1] for call in message.tool_calls}
    return any(key(call) in earlier for call in ai_messages[-1].tool_calls)


def _conversation_id() -> str | None:
    """The thread id for log lines; `None` outside a run, so error handling cannot raise."""
    try:
        return get_config()["configurable"]["thread_id"]
    except Exception:
        return None


class TurnBoundMiddleware(AgentMiddleware[ChatState, TurnContext]):
    """Ends a turn that runs out of steps or goes round in circles, with a tool-less answer marked in `stopped`."""

    state_schema = ChatState

    async def _wrap_up(
        self,
        request: ModelRequest[TurnContext],
        handler: Callable[[ModelRequest[TurnContext]], Awaitable[ModelResponse]],
    ) -> AIMessage:
        """The final answer of a turn the server ended: a tool-less model call, or the fixed text."""
        try:
            wrap_up_request = request.override(
                tools=[], messages=[*request.messages, SystemMessage(WRAP_UP_INSTRUCTION)]
            )
            answer = (await handler(wrap_up_request)).result[0]
            if answer.text.strip() and not answer.tool_calls:
                return answer
        except Exception as e:
            logger.exception("llm_wrap_up_failed", conversation_id=_conversation_id(), error=str(e))
        return AIMessage(content=STOPPED_FALLBACK_TEXT)

    async def awrap_model_call(
        self,
        request: ModelRequest[TurnContext],
        handler: Callable[[ModelRequest[TurnContext]], Awaitable[ModelResponse]],
    ) -> ModelResponse | ExtendedModelResponse:
        """Pass the response on, or replace a tool-calling one by the wrap-up answer when the turn must stop."""
        response = await handler(request)
        message = response.result[0]

        if not message.tool_calls:
            if not message.text.strip():
                # Not an answer: ending the turn here would store an empty reply and show the user nothing.
                # The Responses API reports a cut-off reply as status "incomplete" with no content.
                logger.warning(
                    "llm_empty_response",
                    conversation_id=_conversation_id(),
                    model=message.response_metadata.get("model_name"),
                    status=message.response_metadata.get("status"),
                    incomplete_details=message.response_metadata.get("incomplete_details"),
                )
                raise Exception("the model returned an empty reply")
            return response

        history = request.state["messages"]
        steps = turn_steps(history)
        if steps + 1 >= settings.llm.CHAT_MAX_STEPS:
            reason = "step_limit"
        elif repeated_call([*history, message]):
            reason = "repeated_call"
        else:
            return response

        logger.warning("chat_turn_stopped", conversation_id=_conversation_id(), reason=reason, steps=steps)
        final = await self._wrap_up(request, handler)
        final.id = final.id or str(uuid.uuid4())
        return ExtendedModelResponse(
            model_response=ModelResponse(result=[final]),
            command=Command(update={"stopped": {**request.state.get("stopped", {}), final.id: reason}}),
        )
