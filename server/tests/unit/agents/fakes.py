"""A scripted stand-in for the model that `ask` and `generate_title` take as `model=`."""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig


class FakeModel:
    """Answers each `ainvoke` from a queue (the last entry repeats): a text becomes an AIMessage, an exception is raised.

    `calls` records the messages and config of every call.
    """

    def __init__(self, *answers: str | list | BaseException) -> None:
        self._answers = list(answers)
        self.calls: list[tuple[list[BaseMessage], RunnableConfig | None]] = []

    async def ainvoke(self, messages: list[BaseMessage], config: RunnableConfig | None = None, **_: Any) -> AIMessage:
        self.calls.append((messages, config))
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        if isinstance(answer, BaseException):
            raise answer
        return AIMessage(content=answer)
