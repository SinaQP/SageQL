"""OpenAI-compatible chat adapter for report-planning conversations."""

from typing import Any, Sequence

from sageql.conversation import ChatError, LLMConfig, Message


_INSTRUCTIONS = (
    "You are SageQL's report-planning assistant. Help the user clarify the "
    "report they want. Ask concise, relevant follow-up questions about the "
    "metrics, filters, time range, grouping, and desired output when needed. "
    "Do not claim to have connected to a database, inspected data, generated "
    "SQL, or created a report. This conversation is only the first step."
)


class OpenAIChatProvider:
    """Use a configurable OpenAI-compatible Chat Completions endpoint."""

    def __init__(self, config: LLMConfig, client: Any = None) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ChatError(
                    "install the OpenAI extra: pip install 'sageql[openai]'"
                ) from exc
            try:
                client = OpenAI(api_key=config.api_key, base_url=config.base_url)
            except Exception as exc:
                raise ChatError("could not initialize the chat provider") from exc
        self._client = client
        self._model = config.model

    def reply(self, messages: Sequence[Message]) -> str:
        request_messages = [{"role": "system", "content": _INSTRUCTIONS}]
        request_messages.extend(
            {"role": message.role, "content": message.content} for message in messages
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=request_messages,
            )
            answer = response.choices[0].message.content
        except Exception as exc:
            raise ChatError("model request failed") from exc
        if not isinstance(answer, str) or not answer.strip():
            raise ChatError("model returned an empty answer")
        return answer
